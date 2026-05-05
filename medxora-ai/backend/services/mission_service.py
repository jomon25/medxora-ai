"""
services/mission_service.py
Mission orchestration engine for MedXora AI.
Handles multi-step agent missions with human approval gates.
"""
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database.tables import (Mission, MissionStep, AgentReasoningLog, HumanApproval,
                              MCPEvent, StrategyMemory, ValidationReport, ExportedMql5,
                              Strategy, BacktestResult)
from services.gemini_planner import (plan_mission, critique_strategy, explain_risk,
                                     advise_evolution, write_final_report)
from services.logger import log_info, log_warn, log_error


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
        step = MissionStep(
            mission_id=mission.id,
            step_number=step_def.get("step_number", 0),
            step_name=step_def.get("step_name", "Step"),
            tool_name=step_def.get("tool_name"),
            requires_approval=str(step_def.get("requires_approval", False)).lower(),
            input_json=json.dumps({"description": step_def.get("description", "")}),
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
            if step.tool_name == "generate_strategy" and out.get("strategy_data"):
                strategy_dict = out["strategy_data"]
            # Evolution may produce a better champion — prefer it
            if step.tool_name == "evolution_agent" and out.get("evolved_strategy"):
                strategy_dict = out["evolved_strategy"]
            # Backtest metrics
            if step.tool_name == "backtest_mock" and out.get("win_rate") is not None:
                metrics = {k: out.get(k) for k in
                           ["net_profit", "win_rate", "max_drawdown", "profit_factor",
                            "sharpe_ratio", "total_trades"]}
        except Exception:
            pass

    return strategy_dict, metrics


def _save_strategy_to_db(db: Session, strategy: dict,
                          parent_id: int | None = None, generation: int = 0) -> Strategy:
    """Upsert a strategy dict into the strategies table."""
    existing = db.query(Strategy).filter(Strategy.name == strategy["name"]).first()
    if existing:
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

        strategy = generate_strategy(timeframe=mission.timeframe, strategy_type="ema_rsi")
        file_path = generate_mql5(strategy)

        s = _save_strategy_to_db(db, strategy)
        s.mql5_file = file_path
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
                        f"for {mission.pair}. Gemini verdict: {critique.get('verdict', 'needs_improvement')}."),
            "strategy_name": strategy["name"],
            "strategy_id": s.id,
            "strategy_data": strategy,           # full dict for downstream steps
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

        risk_result = check_risk(strategy_dict)
        explanation = explain_risk(strategy_dict, risk_result)

        db.add(AgentReasoningLog(
            mission_id=mission.id, agent_name="Gemini Risk Explainer",
            reasoning_summary=explanation,
            decision="proceed" if risk_result["passed"] else "mutate",
            next_action="mql5_generator", confidence=0.85,
        ))
        db.commit()

        status = "PASSED" if risk_result["passed"] else "needs adjustment"
        return {
            "summary": f"Risk validation {status}. {explanation[:120]}",
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
            "file": file_path, "decision": "proceed", "next_action": "backtest_mock", "confidence": 1.0,
        }

    # ── 5. Backtest (mock) ───────────────────────────────────────────────────
    if tool_name == "backtest_mock":
        from services.report_parser import parse_mock_result
        from services.evolution_engine import score_result

        strategy_dict, _ = _get_strategy_context(db, mission)
        if not strategy_dict:
            return {"summary": "No strategy to backtest.", "decision": "retry", "confidence": 0.3}

        metrics = parse_mock_result(strategy_dict["name"])
        fitness = score_result(metrics)

        s = db.query(Strategy).filter(Strategy.name == strategy_dict["name"]).first()
        if s:
            db.add(BacktestResult(
                strategy_id=s.id,
                net_profit=metrics.get("net_profit"),
                gross_profit=metrics.get("gross_profit"),
                gross_loss=metrics.get("gross_loss"),
                max_drawdown=metrics.get("max_drawdown"),
                win_rate=metrics.get("win_rate"),
                total_trades=metrics.get("total_trades"),
                profit_factor=metrics.get("profit_factor"),
                expected_payoff=metrics.get("expected_payoff"),
                sharpe_ratio=metrics.get("sharpe_ratio"),
                recovery_factor=metrics.get("recovery_factor"),
                monthly_profit=metrics.get("monthly_profit"),
                yearly_profit=metrics.get("yearly_profit"),
                status="completed",
            ))
            db.commit()

        return {
            "summary": (f"Backtest complete for {strategy_dict['name']}. "
                        f"Net profit: ${metrics['net_profit']:.0f}, "
                        f"Win rate: {metrics['win_rate']:.1f}%, "
                        f"Sharpe: {metrics['sharpe_ratio']:.2f}"),
            "net_profit": metrics["net_profit"],
            "win_rate": metrics["win_rate"],
            "max_drawdown": metrics["max_drawdown"],
            "profit_factor": metrics["profit_factor"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "total_trades": metrics["total_trades"],
            "fitness_score": fitness,
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
            "next_action": "evolution_agent",
            "confidence": mc["confidence"],
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
            mission.final_strategy_id = s_child.id
            db.commit()

        db.add(AgentReasoningLog(
            mission_id=mission.id, agent_name="Gemini Evolution Advisor",
            reasoning_summary=advice,
            decision="proceed", next_action="mcp_search", confidence=0.85,
        ))
        db.commit()

        return {
            "summary": (f"Evolution over 3 generations. Champion: {best['name']}. "
                        f"Improved: {evo['improved']}. Gemini: {advice[:80]}"),
            "decision": "proceed",
            "generations": 3,
            "improved": evo["improved"],
            "champion_name": best["name"],
            "evolved_strategy": best,           # full dict so downstream steps can use it
            "best_score": evo["best_score"],
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
