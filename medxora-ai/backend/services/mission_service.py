"""
services/mission_service.py
Mission orchestration engine for MedXora AI.
Handles multi-step agent missions with human approval gates.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from database.tables import (Mission, MissionStep, AgentReasoningLog, HumanApproval,
                              MCPEvent, StrategyMemory, ValidationReport, ExportedMql5,
                              Strategy, BacktestResult, WalkForwardResult)
from services.gemini_planner import (plan_mission, critique_strategy, explain_risk,
                                     advise_evolution, write_final_report)
from services.logger import log_info, log_warn, log_error

REAL_BACKTEST_TOOL_NAMES = {"backtest_mock", "backtest_real_data", "backtest_eurusd_tick"}
MISSION_METRIC_KEYS = [
    "net_profit",
    "gross_profit",
    "gross_loss",
    "max_drawdown",
    "win_rate",
    "total_trades",
    "profit_factor",
    "expected_payoff",
    "sharpe_ratio",
    "recovery_factor",
    "monthly_profit",
    "yearly_profit",
]


# ── Mission lifecycle ──────────────────────────────────────────────────────────

def create_mission(db: Session, user_goal: str, pair: str = "EURUSD", timeframe: str = "M15") -> Mission:
    """Create a new mission and generate Gemini plan."""
    plan = plan_mission(user_goal, pair, timeframe)
    mission = Mission(
        user_goal=user_goal, pair=pair, timeframe=timeframe,
        status="pending",
        plan_json=json.dumps(plan.get("steps", [])),
        gemini_reasoning=f"Plan created: {plan.get('plan_summary', 'Mission started')}",
    )
    db.add(mission)
    db.flush()

    for step_def in plan.get("steps", []):
        normalized = _normalize_plan_step(step_def)
        step = MissionStep(
            mission_id=mission.id,
            step_number=normalized.get("step_number", 0),
            step_name=normalized.get("step_name", "Step"),
            tool_name=normalized.get("tool_name"),
            requires_approval=str(normalized.get("requires_approval", False)).lower(),
            input_json=json.dumps({"description": normalized.get("description", "")}),
        )
        db.add(step)

    db.commit()
    db.refresh(mission)
    log_info("mission_service", f"Mission {mission.id} created: {user_goal[:60]}")
    return mission


def get_mission(db: Session, mission_id: int) -> Mission | None:
    return db.query(Mission).filter(Mission.id == mission_id).first()


def list_missions(db: Session, limit: int = 20) -> list:
    return db.query(Mission).order_by(Mission.created_at.desc()).limit(limit).all()


def advance_mission(db: Session, mission_id: int) -> dict:
    """Execute the next pending step of a mission. Returns status dict."""
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return {"error": "Mission not found"}
    if mission.status in ("completed", "failed", "stopped"):
        return {"status": mission.status, "message": "Mission already finished"}

    pending_steps = (db.query(MissionStep)
                     .filter(MissionStep.mission_id == mission_id, MissionStep.status == "pending")
                     .order_by(MissionStep.step_number).all())

    if not pending_steps:
        failed_count = (db.query(MissionStep)
                        .filter(MissionStep.mission_id == mission_id,
                                MissionStep.status == "failed")
                        .count())
        if failed_count > 0:
            mission.status = "failed"
            mission.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed",
                    "message": f"Mission failed: {failed_count} step(s) encountered errors"}
        mission.status = "completed"
        mission.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "completed", "message": "All steps done"}

    step = pending_steps[0]

    if str(step.requires_approval).lower() == "true":
        step.status = "waiting_approval"
        mission.status = "waiting_approval"
        db.commit()
        return {"status": "waiting_approval", "step": step.as_dict(),
                "message": f"Approval required for: {step.step_name}"}

    _execute_step(db, mission, step)
    return {"status": mission.status, "step": step.as_dict(), "message": f"Executed: {step.step_name}"}


def _execute_step(db: Session, mission: Mission, step: MissionStep):
    """Execute a mission step and store results."""
    step.status = "running"
    mission.status = "running"
    db.commit()

    try:
        result = _run_tool(db, step.tool_name, mission, step)
        step.output_json = json.dumps(result)
        step.status = "completed"
        step.completed_at = datetime.now(timezone.utc)

        reasoning = AgentReasoningLog(
            mission_id=mission.id,
            agent_name=step.tool_name or "system",
            reasoning_summary=result.get("summary", f"Executed {step.step_name}"),
            decision=result.get("decision", "proceed"),
            next_action=result.get("next_action", "continue to next step"),
            confidence=result.get("confidence", 0.8),
        )
        db.add(reasoning)
        mission.gemini_reasoning = result.get("summary", f"Step {step.step_name} completed.")
        db.commit()
        log_info("mission_service", f"Step {step.step_number} '{step.step_name}' done for mission {mission.id}")
    except Exception as e:
        step.status = "failed"
        step.error_message = str(e)
        mission.status = "failed"
        db.commit()
        log_error("mission_service", f"Step {step.step_number} failed: {e}")


# ── State helpers ──────────────────────────────────────────────────────────────

def _normalize_plan_step(step_def: dict) -> dict:
    normalized = dict(step_def or {})
    tool_name = normalized.get("tool_name")
    step_name = normalized.get("step_name", "Step")
    description = normalized.get("description", "")
    if tool_name == "backtest_mock":
        normalized["tool_name"] = "backtest_eurusd_tick"
        normalized["step_name"] = (
            step_name.replace("Mock", "Real Tick").replace("mock", "real tick")
            if "mock" in step_name.lower()
            else "Run EURUSD Real Tick Backtest"
        )
        normalized["description"] = description or "Backtest against EURUSD real tick-derived OHLCV data."
    return normalized


def _extract_metric_payload(payload: dict | None) -> dict | None:
    payload = payload or {}
    source = payload.get("latest_backtest") if isinstance(payload.get("latest_backtest"), dict) else payload
    metrics = {key: source.get(key) for key in MISSION_METRIC_KEYS if source.get(key) is not None}
    return metrics or None


def _get_latest_backtest(db: Session, strategy_id: int | None) -> BacktestResult | None:
    if not strategy_id:
        return None
    return (
        db.query(BacktestResult)
        .filter(BacktestResult.strategy_id == strategy_id)
        .order_by(BacktestResult.created_at.desc())
        .first()
    )


def _load_backtest_report_metadata(report_file: str | None) -> dict:
    if not report_file:
        return {}
    path = Path(report_file)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "initial_balance": payload.get("initial_balance"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "data_source": payload.get("data_source"),
        "report_file": payload.get("report_file") or report_file,
    }


def _serialize_strategy_snapshot(strategy_row: Strategy | None, latest_backtest: BacktestResult | None = None) -> dict | None:
    if not strategy_row:
        return None
    payload = strategy_row.as_dict()
    metrics = latest_backtest.as_dict() if latest_backtest else None
    if metrics and latest_backtest:
        metrics.update(_load_backtest_report_metadata(latest_backtest.report_file))
    payload["latest_backtest"] = metrics
    if metrics:
        for key in MISSION_METRIC_KEYS:
            payload[key] = metrics.get(key)
        payload["data_source"] = metrics.get("data_source", "EURUSD real tick-derived OHLCV")
        payload["initial_balance"] = metrics.get("initial_balance")
        payload["start_date"] = metrics.get("start_date")
        payload["end_date"] = metrics.get("end_date")
    payload["mql5_file"] = strategy_row.mql5_file
    return payload


def get_mission_strategy_snapshot(db: Session, mission: Mission) -> dict | None:
    strategy_row = None

    if mission.final_strategy_id:
        strategy_row = db.query(Strategy).filter(Strategy.id == mission.final_strategy_id).first()

    strategy_dict, metrics = _get_strategy_context(db, mission)
    if not strategy_row and strategy_dict:
        strategy_row = db.query(Strategy).filter(Strategy.name == strategy_dict.get("name")).first()

    latest_backtest = _get_latest_backtest(db, strategy_row.id if strategy_row else None)
    if strategy_row:
        snapshot = _serialize_strategy_snapshot(strategy_row, latest_backtest)
        if snapshot:
            if not snapshot.get("latest_backtest") and metrics:
                snapshot["latest_backtest"] = metrics
                for key in MISSION_METRIC_KEYS:
                    if metrics.get(key) is not None:
                        snapshot[key] = metrics.get(key)
            snapshot["mission_pair"] = mission.pair
            snapshot["mission_timeframe"] = mission.timeframe
            return snapshot

    if not strategy_dict:
        return None

    snapshot = {
        "id": None,
        "name": strategy_dict.get("name"),
        "symbol": strategy_dict.get("symbol", mission.pair),
        "timeframe": strategy_dict.get("timeframe", mission.timeframe),
        "strategy_type": strategy_dict.get("strategy_type", "strategy"),
        "generation": strategy_dict.get("generation", 0),
        "parameters": strategy_dict.get("parameters", {}),
        "latest_backtest": metrics,
        "mission_pair": mission.pair,
        "mission_timeframe": mission.timeframe,
    }
    if metrics:
        snapshot.update(metrics)
        snapshot["data_source"] = metrics.get("data_source", "EURUSD real tick-derived OHLCV")
    return snapshot


def _ensure_real_tick_ohlcv(timeframe: str) -> str:
    from services.mt5_ohlcv_generator import OUTPUT_DIR, generate_ohlcv_from_mt5_ticks
    from services.mt5_tick_converter import PARQUET_PATH, convert_mt5_ticks_to_parquet

    target_path = Path(OUTPUT_DIR) / f"EURUSD_{timeframe}.parquet"
    if target_path.exists():
        return str(target_path)

    if not Path(PARQUET_PATH).exists():
        convert_mt5_ticks_to_parquet()

    generate_ohlcv_from_mt5_ticks()
    if not target_path.exists():
        raise FileNotFoundError(f"Real EURUSD OHLCV dataset is missing for {timeframe}.")

    return str(target_path)


def _run_real_backtest_for_strategy(db: Session, mission: Mission, strategy_dict: dict, strategy_row: Strategy | None = None) -> dict:
    from services.backtest_engine import run_ema_backtest
    from services.evolution_engine import score_result

    params = strategy_dict.get("parameters", {})
    timeframe = strategy_dict.get("timeframe", mission.timeframe)
    _ensure_real_tick_ohlcv(timeframe)

    raw_result = run_ema_backtest(
        symbol="EURUSD",
        timeframe=timeframe,
        fast_ema=int(params.get("fast_ema", params.get("macd_fast", 14)) or 14),
        slow_ema=int(params.get("slow_ema", params.get("macd_slow", 50)) or 50),
        initial_balance=5000.0,
    )
    strategy_row = strategy_row or db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()

    metrics = {
        "net_profit": raw_result.get("net_profit"),
        "gross_profit": raw_result.get("gross_profit"),
        "gross_loss": raw_result.get("gross_loss"),
        "max_drawdown": raw_result.get("max_drawdown_pct"),
        "win_rate": raw_result.get("win_rate"),
        "total_trades": raw_result.get("total_trades"),
        "profit_factor": raw_result.get("profit_factor"),
        "expected_payoff": raw_result.get("expected_payoff"),
        "sharpe_ratio": raw_result.get("sharpe_ratio"),
        "recovery_factor": raw_result.get("recovery_factor"),
        "monthly_profit": raw_result.get("monthly_profit"),
        "yearly_profit": raw_result.get("yearly_profit"),
    }

    if strategy_row:
        db.add(BacktestResult(
            strategy_id=strategy_row.id,
            net_profit=metrics["net_profit"],
            gross_profit=metrics["gross_profit"],
            gross_loss=metrics["gross_loss"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            total_trades=metrics["total_trades"],
            profit_factor=metrics["profit_factor"],
            expected_payoff=metrics["expected_payoff"],
            sharpe_ratio=metrics["sharpe_ratio"],
            recovery_factor=metrics["recovery_factor"],
            monthly_profit=metrics["monthly_profit"],
            yearly_profit=metrics["yearly_profit"],
            report_file=raw_result.get("report_file"),
            status="completed",
        ))
        db.commit()

    return {
        **metrics,
        "strategy_id": strategy_row.id if strategy_row else None,
        "fitness_score": score_result(metrics),
        "backtest_mode": "real_tick_data",
        "data_source": raw_result.get("data_source", "EURUSD real tick-derived OHLCV"),
        "initial_balance": raw_result.get("initial_balance"),
        "start_date": raw_result.get("start_date"),
        "end_date": raw_result.get("end_date"),
        "final_equity": raw_result.get("final_equity"),
        "bars": raw_result.get("bars"),
        "average_spread_pips": raw_result.get("average_spread_pips"),
        "equity_curve": raw_result.get("equity_curve", []),
        "report_file": raw_result.get("report_file"),
    }


def _get_strategy_context(db: Session, mission: Mission) -> tuple:
    """Retrieve current champion strategy dict and backtest metrics from completed step outputs."""
    strategy_dict = None
    metrics = None

    completed = (db.query(MissionStep)
                 .filter(MissionStep.mission_id == mission.id, MissionStep.status == "completed")
                 .order_by(MissionStep.step_number).all())

    for step in completed:
        if not step.output_json:
            continue
        try:
            out = json.loads(step.output_json)
            # Full original strategy stored in generate_strategy output
            if out.get("strategy_data"):
                strategy_dict = out["strategy_data"]
            # Evolution may produce a better champion — prefer it
            if out.get("evolved_strategy"):
                strategy_dict = out["evolved_strategy"]
            # Backtest metrics
            extracted = _extract_metric_payload(out)
            if extracted:
                metrics = extracted
        except Exception:
            pass

    if mission.final_strategy_id:
        final_row = db.query(Strategy).filter(Strategy.id == mission.final_strategy_id).first()
        if final_row:
            strategy_dict = final_row.as_dict()
            latest_backtest = _get_latest_backtest(db, final_row.id)
            if latest_backtest:
                metrics = _extract_metric_payload(latest_backtest.as_dict()) or metrics

    if strategy_dict and not metrics:
        strategy_row = db.query(Strategy).filter(Strategy.name == strategy_dict.get("name")).first()
        latest_backtest = _get_latest_backtest(db, strategy_row.id if strategy_row else None)
        if latest_backtest:
            metrics = _extract_metric_payload(latest_backtest.as_dict())

    return strategy_dict, metrics


def _save_strategy_to_db(db: Session, strategy: dict,
                          parent_id: int | None = None, generation: int = 0) -> Strategy:
    """Upsert a strategy dict into the strategies table."""
    existing = db.query(Strategy).filter(Strategy.name == strategy["name"]).first()
    if existing:
        # Update parameters_json if the existing row is missing it
        if not existing.parameters_json:
            existing.parameters_json = json.dumps(strategy.get("parameters", {}))
            db.commit()
        return existing
    p = strategy.get("parameters", {})
    s = Strategy(
        name=strategy["name"],
        symbol=strategy.get("symbol", "EURUSD"),
        timeframe=strategy.get("timeframe", "M15"),
        type=strategy.get("strategy_type", "trend_following"),
        fast_ema=p.get("fast_ema"),
        slow_ema=p.get("slow_ema"),
        rsi_period=p.get("rsi_period"),
        rsi_buy=p.get("rsi_buy"),
        rsi_sell=p.get("rsi_sell"),
        stop_loss=p.get("stop_loss", 300),
        take_profit=p.get("take_profit", 600),
        risk_percent=p.get("risk_percent", 1.0),
        parameters_json=json.dumps(strategy.get("parameters", {})),  # full params preserved
        parent_id=parent_id,
        generation=generation,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ── Tool dispatch ──────────────────────────────────────────────────────────────

def _run_tool(db: Session, tool_name: str, mission: Mission, step: MissionStep) -> dict:
    """Execute a real agent tool and return a result dict."""

    # ── 1. Gemini Planner ────────────────────────────────────────────────────
    if tool_name == "gemini_planner":
        from services.gemini_planner import route_tool
        routing = route_tool("mission_start", {"goal": mission.user_goal, "pair": mission.pair})
        return {
            "summary": f"Gemini analysed goal: '{mission.user_goal[:80]}'. Routing confirmed.",
            "decision": "proceed", "next_action": "generate_strategy", "confidence": 0.95,
            "gemini_routing": routing,
        }

    # ── 2. Generate Strategy ─────────────────────────────────────────────────
    if tool_name == "generate_strategy":
        from agents.strategy_creator import generate_strategy
        from services.mql5_generator import generate_mql5

        strategy = generate_strategy(
            timeframe=mission.timeframe,
            strategy_type="ema_rsi",
            mission_brief=mission.user_goal,
        )
        file_path = generate_mql5(strategy)

        s = _save_strategy_to_db(db, strategy)
        s.mql5_file = file_path
        mission.final_strategy_id = s.id
        db.commit()

        critique = critique_strategy(strategy)
        db.add(AgentReasoningLog(
            mission_id=mission.id, agent_name="Gemini Strategy Critic",
            reasoning_summary=critique.get("recommendation", "Strategy reviewed by Gemini AI."),
            decision=critique.get("verdict", "needs_improvement"),
            next_action="validate_risk",
            confidence=critique.get("quality_score", 65) / 100.0,
        ))
        db.commit()

        return {
            "summary": (f"Generated {strategy['strategy_type']} strategy {strategy['name']} "
                        f"for {mission.pair} using {strategy.get('generation_source', 'mission pipeline')}. "
                        f"Gemini verdict: {critique.get('verdict', 'needs_improvement')}."),
            "strategy_name": strategy["name"],
            "strategy_id": s.id,
            "strategy_data": strategy,           # full dict for downstream steps
            "strategy_generation_source": strategy.get("generation_source"),
            "file": file_path,
            "gemini_critique": critique,
            "decision": "proceed", "next_action": "validate_risk", "confidence": 0.9,
        }

    # ── 3. Risk Manager ──────────────────────────────────────────────────────
    if tool_name == "risk_manager":
        from agents.risk_manager import check_risk

        strategy_dict, _ = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy found to validate.", "decision": "retry", "confidence": 0.3}

        risk_result = check_risk(strategy_dict, db=db)
        explanation = explain_risk(strategy_dict, risk_result)

        db.add(AgentReasoningLog(
            mission_id=mission.id, agent_name="Gemini Risk Explainer",
            reasoning_summary=explanation.get("summary", "Risk explanation generated."),
            decision="proceed" if risk_result["passed"] else "mutate",
            next_action="mql5_generator", confidence=0.85,
        ))
        db.commit()

        status = "PASSED" if risk_result["passed"] else "needs adjustment"
        return {
            "summary": f"Risk validation {status}. {explanation.get('summary', '')[:120]}",
            "passed": risk_result["passed"],
            "issues": risk_result.get("issues", []),
            "warnings": risk_result.get("warnings", []),
            "gemini_explanation": explanation,
            "decision": "proceed", "next_action": "mql5_generator", "confidence": 0.85,
        }

    # ── 4. MQL5 Generator ────────────────────────────────────────────────────
    if tool_name == "mql5_generator":
        from services.mql5_generator import generate_mql5

        strategy_dict, _ = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy to generate MQL5 for.", "decision": "retry", "confidence": 0.3}

        file_path = generate_mql5(strategy_dict)
        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        if s and file_path:
            s.mql5_file = file_path
            db.commit()

        return {
            "summary": f"MQL5 Expert Advisor code generated: {strategy_dict['name']}.mq5",
            "file": file_path, "decision": "proceed", "next_action": "backtest_eurusd_tick", "confidence": 1.0,
        }

    # ── 5. Backtest (mock) ───────────────────────────────────────────────────
    if tool_name in REAL_BACKTEST_TOOL_NAMES:
        strategy_dict, _ = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy to backtest.", "decision": "retry", "confidence": 0.3}

        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        metrics = _run_real_backtest_for_strategy(db, mission, strategy_dict, strategy_row=s)

        return {
            "summary": (f"EURUSD real tick backtest complete for {strategy_dict['name']}. "
                        f"Net profit: ${float(metrics['net_profit'] or 0):.0f}, "
                        f"Win rate: {float(metrics['win_rate'] or 0):.1f}%, "
                        f"Sharpe: {float(metrics['sharpe_ratio'] or 0):.2f}"),
            "net_profit": metrics["net_profit"],
            "gross_profit": metrics["gross_profit"],
            "gross_loss": metrics["gross_loss"],
            "win_rate": metrics["win_rate"],
            "max_drawdown": metrics["max_drawdown"],
            "profit_factor": metrics["profit_factor"],
            "expected_payoff": metrics["expected_payoff"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "recovery_factor": metrics["recovery_factor"],
            "monthly_profit": metrics["monthly_profit"],
            "yearly_profit": metrics["yearly_profit"],
            "total_trades": metrics["total_trades"],
            "strategy_id": metrics["strategy_id"],
            "fitness_score": metrics["fitness_score"],
            "latest_backtest": metrics,
            "data_source": metrics["data_source"],
            "decision": "proceed", "next_action": "report_parser", "confidence": 0.8,
        }

    # ── 6. Report Parser ─────────────────────────────────────────────────────
    if tool_name == "report_parser":
        _, metrics = _get_strategy_context(db, mission)
        if not metrics:
            return {"summary": "No backtest metrics to parse.", "decision": "proceed", "confidence": 0.7}

        sharpe = metrics.get("sharpe_ratio") or 0
        dd = metrics.get("max_drawdown") or 0
        return {
            "summary": f"Metrics parsed: Sharpe {sharpe:.2f}, Drawdown {dd:.1f}%. Ready for fitness scoring.",
            "metrics": metrics,
            "decision": "proceed", "next_action": "fitness_scorer", "confidence": 0.9,
        }

    # ── 7. Fitness Scorer ────────────────────────────────────────────────────
    if tool_name == "fitness_scorer":
        from services.evolution_engine import score_result

        _, metrics = _get_strategy_context(db, mission)
        if not metrics:
            return {"summary": "No metrics for fitness scoring.", "score": 0,
                    "decision": "proceed", "confidence": 0.5}

        score = score_result(metrics)
        quality = "qualifies" if score > 400 else "borderline"
        return {
            "summary": f"Fitness score: {score:.1f} — strategy {quality} for evolution.",
            "score": score,
            "decision": "proceed", "next_action": "monte_carlo_agent", "confidence": 0.85,
        }

    # ── 8. Monte Carlo Agent ─────────────────────────────────────────────────
    if tool_name == "monte_carlo_agent":
        from agents.monte_carlo_agent import run_monte_carlo_agent

        strategy_dict, metrics = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy for Monte Carlo.", "decision": "proceed", "confidence": 0.5}

        mc = run_monte_carlo_agent(strategy_dict, metrics)
        data = mc.get("data", {})

        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        if s:
            robustness = round((1.0 - data.get("ruin_probability", 0.1)) * 100, 1)
            risk_score = round((1.0 - min(data.get("avg_max_drawdown_pct", 15.0), 100) / 100) * 100, 1)
            db.add(ValidationReport(
                strategy_id=s.id,
                validation_type="monte_carlo",
                robustness_score=max(0.0, robustness),
                risk_score=max(0.0, risk_score),
                passed=str(mc["decision"] in ("approve", "needs_retest")).lower(),
                summary=mc["reason"],
                details_json=json.dumps(data),
            ))
            db.commit()

        return {
            "summary": mc["reason"],
            "decision": "proceed",
            "mc_decision": mc["decision"],
            "risk_level": mc["risk_level"],
            "evidence": mc["evidence"],
            "ruin_probability": data.get("ruin_probability"),
            "expected_return_pct": data.get("expected_return_pct"),
            "next_action": "walk_forward_agent",
            "confidence": mc["confidence"],
        }

    # -- 8.5 Walk-Forward Validation ---------------------------------------------------
    if tool_name == "walk_forward_agent":
        from services.agent_orchestrator import _run_walk_forward_agent

        strategy_dict, metrics = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy for walk-forward validation.", "decision": "retry", "confidence": 0.4}

        wf = _run_walk_forward_agent(strategy_dict, metrics)
        data = wf.get("data", {})
        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        if s:
            db.add(WalkForwardResult(
                strategy_id=s.id,
                windows_json=json.dumps(data.get("windows", [])),
                consistency_score=float(data.get("consistency_score", 0) or 0),
                is_avg_profit=float(sum(w.get("in_sample_pf", 0) for w in data.get("windows", [])) / max(len(data.get("windows", [])), 1)),
                oos_avg_profit=float(data.get("average_out_of_sample_pf", 0) or 0),
                degradation_pct=float(data.get("degradation_pct", 0) or 0),
                passed=str(wf.get("decision") in ("approve", "needs_retest")).lower(),
            ))
            db.add(ValidationReport(
                strategy_id=s.id,
                validation_type="walk_forward",
                robustness_score=float(data.get("consistency_score", 0) or 0),
                risk_score=float(max(0.0, 100.0 - float(data.get("degradation_pct", 0) or 0))),
                passed=str(wf.get("decision") in ("approve", "needs_retest")).lower(),
                summary=wf.get("reason"),
                details_json=json.dumps(data),
            ))
            db.commit()

        return {
            "summary": wf["reason"],
            "decision": "proceed",
            "walk_forward_decision": wf["decision"],
            "consistency_score": data.get("consistency_score"),
            "degradation_pct": data.get("degradation_pct"),
            "windows": data.get("windows", []),
            "next_action": "evolution_agent",
            "confidence": wf["confidence"],
        }

    # ── 9. Evolution Agent ───────────────────────────────────────────────────
    if tool_name == "evolution_agent":
        from agents.evolution_agent import run_evolution
        from services.mql5_generator import generate_mql5

        strategy_dict, _ = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy to evolve.", "decision": "proceed", "confidence": 0.5}

        evo = run_evolution(strategy_dict, generations=3)
        best = evo["evolved"]
        child_scores = [g["best_score"] for g in evo["generations"]]
        advice = advise_evolution(strategy_dict, child_scores, generation=3)
        backtest_metrics = None

        if evo["improved"]:
            s_parent = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
            s_child = _save_strategy_to_db(
                db, best,
                parent_id=s_parent.id if s_parent else None,
                generation=(s_parent.generation + 1 if s_parent else 1),
            )
            try:
                file_path = generate_mql5(best)
                s_child.mql5_file = file_path
                db.commit()
            except Exception:
                pass
            try:
                backtest_metrics = _run_real_backtest_for_strategy(db, mission, best, strategy_row=s_child)
            except Exception as backtest_error:
                log_error("mission_service", f"Evolution backtest failed for {best.get('name')}: {backtest_error}")
            mission.final_strategy_id = s_child.id
            db.commit()

        db.add(AgentReasoningLog(
            mission_id=mission.id, agent_name="Gemini Evolution Advisor",
            reasoning_summary=advice.get("summary", "Evolution advice generated."),
            decision="proceed", next_action="mcp_search", confidence=0.85,
        ))
        db.commit()

        return {
            "summary": (f"Evolution over 3 generations. Champion: {best['name']}. "
                        f"Improved: {evo['improved']}. Gemini: {advice.get('summary', '')[:80]}"),
            "decision": "proceed",
            "generations": 3,
            "improved": evo["improved"],
            "champion_name": best["name"],
            "evolved_strategy": best,           # full dict so downstream steps can use it
            "best_score": evo["best_score"],
            "latest_backtest": backtest_metrics if evo["improved"] else None,
            "gemini_advice": advice,
            "next_action": "mcp_search", "confidence": 0.85,
        }

    # ── 10. MCP Search / Memory ──────────────────────────────────────────────
    if tool_name == "mcp_search":
        from services.mcp_service import search_strategies, save_strategy_memory

        strategy_dict, metrics = _get_strategy_context(db, mission)
        if strategy_dict and metrics:
            save_strategy_memory(db, {
                "strategy_name": strategy_dict["name"],
                "pair": mission.pair,
                "timeframe": mission.timeframe,
                "sharpe": metrics.get("sharpe_ratio"),
                "drawdown": metrics.get("max_drawdown"),
                "win_rate": metrics.get("win_rate"),
                "profit_factor": metrics.get("profit_factor"),
                "risk_status": "approved",
                "tags": ["mission", mission.pair, mission.timeframe],
            }, mission_id=mission.id)

        found = search_strategies(db, {"pair": mission.pair}, mission_id=mission.id)
        return {
            "summary": f"MCP memory saved. Found {len(found)} similar {mission.pair} strategies in memory.",
            "found": len(found),
            "decision": "proceed", "next_action": "ensemble_voting", "confidence": 0.9,
        }

    # ── 11. Ensemble Voting ──────────────────────────────────────────────────
    if tool_name == "ensemble_voting":
        from agents.ensemble_voting_agent import run_ensemble_voting_agent
        from agents.risk_manager import check_risk
        from agents.monte_carlo_agent import run_monte_carlo_agent
        from agents.sentiment_agent import run_sentiment_agent
        from agents.macro_calendar_agent import run_macro_calendar_agent
        from agents.seasonality_agent import run_seasonality_agent
        from agents.regime_change_detector_agent import run_regime_change_detector_agent
        from agents.drawdown_recovery_agent import run_drawdown_recovery_agent
        from agents.slippage_spread_agent import run_slippage_spread_agent
        from agents.benchmark_comparison_agent import run_benchmark_comparison_agent

        strategy_dict, metrics = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy for ensemble voting.", "decision": "proceed", "confidence": 0.5}

        risk = check_risk(strategy_dict)
        mc = run_monte_carlo_agent(strategy_dict, metrics)
        sr = (metrics or {}).get("sharpe_ratio") or 0.0
        tt = (metrics or {}).get("total_trades") or 0

        agent_decisions = [
            {
                "agent": "Risk Manager Agent",
                "decision": "approve" if risk["passed"] else "reject",
                "confidence": 0.90,
                "risk_level": "low" if risk["passed"] else "high",
            },
            {
                "agent": "Monte Carlo Agent",
                "decision": mc["decision"],
                "confidence": mc["confidence"],
                "risk_level": mc["risk_level"],
            },
            {
                "agent": "Technical Indicator Agent",
                "decision": "approve" if sr > 1.0 else "needs_retest",
                "confidence": 0.70,
                "risk_level": "low" if sr > 1.0 else "medium",
            },
            {
                "agent": "Overfitting Detector Agent",
                "decision": "approve" if tt > 100 else "needs_retest",
                "confidence": 0.80,
                "risk_level": "medium",
            },
        ]

        # ── Wire in the 12 intelligence agents ──────────────────────────────
        def _safe_agent(name, fn, *args):
            """Call an intelligence agent; on error return a neutral needs_retest."""
            try:
                result = fn(*args)
                return {
                    "agent": name,
                    "decision": result.get("decision", "needs_retest"),
                    "confidence": float(result.get("confidence", 0.60)),
                    "risk_level": result.get("risk_level", "medium"),
                }
            except Exception:
                return {"agent": name, "decision": "needs_retest",
                        "confidence": 0.50, "risk_level": "medium"}

        agent_decisions += [
            _safe_agent("Sentiment Analysis Agent",      run_sentiment_agent,              strategy_dict, metrics),
            _safe_agent("Macro Calendar Agent",          run_macro_calendar_agent,         strategy_dict, metrics),
            _safe_agent("Seasonality Agent",             run_seasonality_agent,            strategy_dict, metrics),
            _safe_agent("Regime Change Detector",        run_regime_change_detector_agent, strategy_dict, metrics),
            _safe_agent("Drawdown Recovery Agent",       run_drawdown_recovery_agent,      strategy_dict, metrics),
            _safe_agent("Slippage & Spread Agent",       run_slippage_spread_agent,        strategy_dict, metrics),
            _safe_agent("Benchmark Comparison Agent",    run_benchmark_comparison_agent,   strategy_dict, metrics),
        ]

        result = run_ensemble_voting_agent(agent_decisions)
        votes_for = sum(1 for d in agent_decisions if d["decision"] == "approve")

        return {
            "summary": result["reason"],
            "votes_for": votes_for,
            "votes_against": len(agent_decisions) - votes_for,
            "total_agents": len(agent_decisions),
            "final_decision": result["decision"],
            "evidence": result["evidence"],
            "decision": "proceed", "next_action": "human_approval",
            "confidence": result["confidence"],
        }

    # ── 12. Human Approval ───────────────────────────────────────────────────
    if tool_name == "human_approval":
        return {
            "summary": "Awaiting human approval before MQL5 export. Please review and approve or reject.",
            "decision": "wait", "confidence": 1.0, "next_action": "mql5_export",
        }

    # ── 13. MQL5 Export ──────────────────────────────────────────────────────
    if tool_name == "mql5_export":
        strategy_dict, metrics = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No champion strategy to export.", "decision": "complete", "confidence": 0.5}

        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        vr = (db.query(ValidationReport)
              .filter(ValidationReport.strategy_id == s.id)
              .order_by(ValidationReport.id.desc())
              .first()) if s else None

        report = write_final_report(
            mission_goal=mission.user_goal,
            champion=strategy_dict,
            metrics=metrics or {},
            validation=vr.as_dict() if vr else {},
        )

        db.add(ExportedMql5(
            strategy_id=s.id if s else None,
            mission_id=mission.id,
            file_path=(s.mql5_file or "") if s else "",
            approved_by_human="true",
            gemini_report=report,
        ))
        if s:
            mission.final_strategy_id = s.id
        db.commit()

        return {
            "summary": f"Champion {strategy_dict['name']} exported with human approval. Gemini final report generated.",
            "exported": True,
            "file": (s.mql5_file or "") if s else "",
            "gemini_report_preview": (report or "")[:300],
            "decision": "proceed", "next_action": "gemini_report", "confidence": 1.0,
        }

    # ── 14. Gemini Final Report ──────────────────────────────────────────────
    if tool_name == "gemini_report":
        exported = (db.query(ExportedMql5)
                    .filter(ExportedMql5.mission_id == mission.id)
                    .order_by(ExportedMql5.id.desc())
                    .first())
        report = exported.gemini_report if exported else "Mission completed successfully."
        return {
            "summary": "Final Gemini mission report is ready.",
            "report": report,
            "decision": "complete", "next_action": "none", "confidence": 0.95,
        }

    # ── Fallback ─────────────────────────────────────────────────────────────
    return {"summary": f"Tool '{tool_name}' executed.", "decision": "proceed",
            "confidence": 0.7, "next_action": "continue"}


# ── Approval / control ─────────────────────────────────────────────────────────

def approve_step(db: Session, mission_id: int, step_id: int, approved: bool, notes: str = "") -> dict:
    """Human approves or rejects a waiting step."""
    step = db.query(MissionStep).filter(MissionStep.id == step_id, MissionStep.mission_id == mission_id).first()
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not step or not mission:
        return {"error": "Step or mission not found"}

    approval = HumanApproval(
        mission_id=mission_id, step_id=step_id,
        action_description=f"Human {'approved' if approved else 'rejected'}: {step.step_name}",
        approved="approved" if approved else "rejected",
        notes=notes,
    )
    db.add(approval)

    if approved:
        step.requires_approval = "false"
        step.status = "pending"
        mission.status = "running"
        db.commit()
        _execute_step(db, mission, step)
    else:
        step.status = "skipped"
        mission.status = "paused"
        db.commit()

    return {"status": "approved" if approved else "rejected", "step": step.as_dict()}


def pause_mission(db: Session, mission_id: int) -> dict:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if mission:
        mission.status = "paused"
        db.commit()
    return {"status": "paused"}


def resume_mission(db: Session, mission_id: int) -> dict:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if mission and mission.status == "paused":
        mission.status = "running"
        db.commit()
    return {"status": "running"}


def stop_mission(db: Session, mission_id: int) -> dict:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if mission:
        mission.status = "stopped"
        db.commit()
    return {"status": "stopped"}


def get_reasoning_trace(db: Session, mission_id: int) -> list:
    return (db.query(AgentReasoningLog)
            .filter(AgentReasoningLog.mission_id == mission_id)
            .order_by(AgentReasoningLog.created_at)
            .all())


def run_full_demo_mission(db: Session) -> Mission:
    """One-click judge demo: creates and auto-advances a full mission."""
    mission = create_mission(
        db,
        user_goal="Create a low-risk EURUSD EMA+RSI strategy on M15, backtest it, evolve for 3 generations, validate with Monte Carlo, and export the champion MQL5 EA.",
        pair="EURUSD",
        timeframe="M15",
    )
    mission.status = "running"
    db.commit()

    steps = (db.query(MissionStep)
             .filter(MissionStep.mission_id == mission.id)
             .order_by(MissionStep.step_number).all())

    for step in steps:
        if step.status == "pending":
            if str(step.requires_approval).lower() == "true":
                step.requires_approval = "false"
            _execute_step(db, mission, step)

    mission.status = "completed"
    mission.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mission)
    log_info("mission_service", f"Demo mission {mission.id} completed")
    return mission
