import asyncio

from database.db import SessionLocal
from database.tables import BacktestResult, Strategy

from agents.strategy_creator import generate_strategy
from services.agent_firm import generate_agent_review
from services.logger import log_error, log_info, log_warn
from services.memory_store import (
    store_agent_memory,
    store_failed_reason,
    store_strategy_reflection,
)
from services.mql5_generator import generate_mql5
from services.mt5_config_generator import generate_config, run_backtest
from services.pipeline_checkpoints import latest_checkpoint, list_checkpoints, record_checkpoint
from services.pipeline_ws import manager
from services.report_parser import parse_mock_result, parse_report
from services.timeframes import normalize_timeframe


async def _checkpoint_and_broadcast(db, strategy_name: str, stage: str, status: str, message: str, data=None):
    if strategy_name:
        record_checkpoint(
            db,
            strategy_name=strategy_name,
            stage=stage,
            status=status,
            message=message,
            payload=data,
        )
    log_line = f"{strategy_name or 'pipeline'} | {stage} | {message}"
    normalized_status = (status or "").lower()
    if normalized_status in {"failed", "error", "timeout"}:
        log_error("live_pipeline", log_line)
    elif normalized_status in {"warning", "warn", "needs_evolution", "needs_retest"}:
        log_warn("live_pipeline", log_line)
    else:
        log_info("live_pipeline", log_line)
    await manager.broadcast(stage, status, message, data)


def _strategy_to_dict(row: Strategy) -> dict:
    return {
        "name": row.name,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "strategy_type": row.type,
        "parameters": {
            "fast_ema": row.fast_ema,
            "slow_ema": row.slow_ema,
            "rsi_period": row.rsi_period,
            "rsi_buy": row.rsi_buy,
            "rsi_sell": row.rsi_sell,
            "stop_loss": row.stop_loss,
            "take_profit": row.take_profit,
            "risk_percent": row.risk_percent,
        },
    }


def _db_strategy_kwargs(strategy: dict, file_path: str) -> dict:
    params = strategy["parameters"]
    return {
        "name": strategy["name"],
        "symbol": strategy.get("symbol", "EURUSD"),
        "timeframe": strategy.get("timeframe", "M15"),
        "type": strategy.get("strategy_type", strategy.get("type", "ema_rsi")),
        "fast_ema": params.get("fast_ema", params.get("macd_fast", 14)),
        "slow_ema": params.get("slow_ema", params.get("macd_slow", 50)),
        "rsi_period": params.get("rsi_period", 14),
        "rsi_buy": params.get("rsi_buy", params.get("rsi_filter", 55)),
        "rsi_sell": params.get("rsi_sell", params.get("rsi_filter", 45)),
        "stop_loss": params.get("stop_loss", 300),
        "take_profit": params.get("take_profit", 600),
        "risk_percent": params.get("risk_percent", 1.0),
        "mql5_file": file_path,
    }


def _save_backtest_result(db, strategy_id: int, metrics: dict, report_file: str | None):
    row = BacktestResult(
        strategy_id=strategy_id,
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
        report_file=report_file,
        status="completed",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _store_review_memory(db, strategy_name: str, review_type: str, reviews: dict):
    for payload in reviews.values():
        store_agent_memory(
            db,
            strategy_name=strategy_name,
            agent_name=payload["agent"],
            category=review_type,
            memory_text=payload["reason"],
            confidence=payload.get("confidence"),
            payload=payload,
        )

    approval = reviews["portfolio_manager_agent"]
    store_strategy_reflection(
        db,
        strategy_name=strategy_name,
        reflection_type=review_type,
        summary=f"{approval['review_state']}: {approval['reason']}",
        details=reviews,
    )

    if review_type != "pretrade_review" and approval["review_state"] != "Approved":
        store_failed_reason(
            db,
            strategy_name=strategy_name,
            stage="PORTFOLIO_MANAGER_DECISION",
            reason=approval["reason"],
            details=approval,
        )

    return approval


async def _run_review_cycle(db, strategy: dict, metrics: dict | None, review_type: str):
    reviews = generate_agent_review(strategy, metrics)
    approval = _store_review_memory(db, strategy["name"], review_type, reviews)
    stage_prefix = review_type.upper()

    await _checkpoint_and_broadcast(
        db,
        strategy["name"],
        f"{stage_prefix}_AGENT_REVIEW_COMPLETED",
        "completed",
        f"{review_type.replace('_', ' ').title()} completed",
        reviews,
    )
    await _checkpoint_and_broadcast(
        db,
        strategy["name"],
        f"{stage_prefix}_PORTFOLIO_MANAGER_DECISION",
        "completed",
        approval["review_state"],
        approval,
    )
    return reviews, approval


async def run_live_pipeline(mock: bool = True, timeframe: str = "M15"):
    timeframe = normalize_timeframe(timeframe)
    db = SessionLocal()
    strategy_name: str | None = None

    try:
        await manager.broadcast("START", "running", "Pipeline started", {"timeframe": timeframe, "mock": mock})
        log_info("live_pipeline", f"pipeline | START | Pipeline started ({timeframe}, mock={mock})")

        strategy = generate_strategy(timeframe)
        strategy_name = strategy["name"]
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "STRATEGY_CREATED",
            "completed",
            "Strategy JSON generated",
            strategy,
        )

        pretrade_reviews, pretrade_approval = await _run_review_cycle(
            db,
            strategy,
            None,
            "pretrade_review",
        )

        file_path = await asyncio.to_thread(generate_mql5, strategy)
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "MQL5_GENERATED",
            "completed",
            "MQL5 file generated successfully",
            {"file": file_path},
        )

        db_strategy = Strategy(**_db_strategy_kwargs(strategy, file_path))
        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "SAVED_STRATEGY",
            "completed",
            "Strategy saved to database",
            {"strategy_id": db_strategy.id, "name": db_strategy.name},
        )

        config_path = await asyncio.to_thread(
            generate_config,
            strategy_name=db_strategy.name,
            symbol=db_strategy.symbol,
            period=db_strategy.timeframe,
        )
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "CONFIG_CREATED",
            "completed",
            "MT5 config generated",
            {"config_file": config_path},
        )

        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "BACKTEST_STARTED",
            "running",
            "Starting backtest",
            {"mock": mock},
        )

        if mock:
            metrics = parse_mock_result(db_strategy.name)
            report_file = None
            await _checkpoint_and_broadcast(
                db,
                strategy_name,
                "BACKTEST_COMPLETED",
                "completed",
                "Mock backtest completed",
                metrics,
            )
        else:
            result = await asyncio.to_thread(run_backtest, db_strategy.name)
            await _checkpoint_and_broadcast(
                db,
                strategy_name,
                "BACKTEST_COMPLETED",
                result.get("status", "unknown"),
                "MT5 backtest finished",
                result,
            )

            report_file = result.get("report_file")
            if result.get("status") != "success" or not report_file:
                failure_stage = "mt5_backtest" if result.get("status") != "success" else "report_parsing"
                failure_reason = result.get("message", "No report file found")
                store_failed_reason(
                    db,
                    strategy_name=strategy_name,
                    stage="BACKTEST_COMPLETED",
                    reason=failure_reason,
                    details=result,
                )
                await _checkpoint_and_broadcast(
                    db,
                    strategy_name,
                    "REPORT_PARSED",
                    "failed",
                    failure_reason,
                    result,
                )
                return {
                    "status": "failed",
                    "stage": failure_stage,
                    "strategy": strategy,
                    "strategy_name": strategy_name,
                    "strategy_id": db_strategy.id,
                    "mql5_file": file_path,
                    "config_file": config_path,
                    "pretrade_reviews": pretrade_reviews,
                    "pretrade_portfolio_decision": pretrade_approval,
                    "reason": failure_reason,
                    "mt5_result": result,
                }

            metrics = await asyncio.to_thread(parse_report, report_file)

        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "REPORT_PARSED",
            "completed",
            "Backtest report parsed",
            metrics,
        )

        backtest_result = _save_backtest_result(db, db_strategy.id, metrics, report_file)
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "SAVED_TO_DB",
            "completed",
            "Backtest result saved to database",
            {"backtest_id": backtest_result.id, "strategy_id": db_strategy.id},
        )

        final_reviews, final_approval = await _run_review_cycle(
            db,
            strategy,
            metrics,
            "post_backtest_review",
        )

        payload = {
            "status": "success",
            "strategy": strategy,
            "strategy_name": db_strategy.name,
            "strategy_id": db_strategy.id,
            "backtest_id": backtest_result.id,
            "timeframe": db_strategy.timeframe,
            "mql5_file": file_path,
            "config_file": config_path,
            "report_file": report_file,
            "metrics": metrics,
            "pretrade_reviews": pretrade_reviews,
            "pretrade_portfolio_decision": pretrade_approval,
            "agent_reviews": final_reviews,
            "portfolio_decision": final_approval,
        }
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "DONE",
            "completed",
            "Pipeline completed successfully",
            payload,
        )
        return payload
    except Exception as exc:
        if strategy_name:
            record_checkpoint(
                db,
                strategy_name=strategy_name,
                stage="ERROR",
                status="failed",
                message=str(exc),
                payload={"error": str(exc)},
            )
            store_failed_reason(
                db,
                strategy_name=strategy_name,
                stage="ERROR",
                reason=str(exc),
                details={"error": str(exc)},
            )
        await manager.broadcast("ERROR", "failed", str(exc))
        log_error("live_pipeline", f"{strategy_name or 'pipeline'} | ERROR | {exc}")
        raise
    finally:
        db.close()


async def resume_live_pipeline(strategy_name: str, mock: bool = True):
    db = SessionLocal()
    try:
        row = db.query(Strategy).filter(Strategy.name == strategy_name).first()
        if row is None:
            return {"status": "failed", "reason": "Strategy not found"}

        checkpoint = latest_checkpoint(db, strategy_name)
        strategy = _strategy_to_dict(row)
        await manager.broadcast(
            "RESUME",
            "running",
            f"Resuming pipeline from {checkpoint.stage if checkpoint else 'saved strategy'}",
            checkpoint.as_dict() if checkpoint else {"strategy_name": strategy_name},
        )
        log_info(
            "live_pipeline",
            f"{strategy_name} | RESUME | Resuming pipeline from {checkpoint.stage if checkpoint else 'saved strategy'}",
        )

        if not row.mql5_file:
            row.mql5_file = await asyncio.to_thread(generate_mql5, strategy)
            db.commit()
            db.refresh(row)
            await _checkpoint_and_broadcast(
                db,
                strategy_name,
                "MQL5_GENERATED",
                "completed",
                "MQL5 file regenerated during resume",
                {"file": row.mql5_file},
            )

        config_path = await asyncio.to_thread(
            generate_config,
            strategy_name=row.name,
            symbol=row.symbol,
            period=row.timeframe,
        )
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "CONFIG_CREATED",
            "completed",
            "MT5 config generated during resume",
            {"config_file": config_path},
        )

        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "BACKTEST_STARTED",
            "running",
            "Restarting backtest from checkpoint",
            {"mock": mock},
        )

        if mock:
            metrics = parse_mock_result(strategy_name)
            report_file = None
        else:
            result = await asyncio.to_thread(run_backtest, strategy_name)
            report_file = result.get("report_file")
            if result.get("status") != "success" or not report_file:
                store_failed_reason(
                    db,
                    strategy_name=strategy_name,
                    stage="BACKTEST_COMPLETED",
                    reason=result.get("message", "Backtest failed on resume"),
                    details=result,
                )
                return {
                    "status": "failed",
                    "strategy_name": strategy_name,
                    "reason": result.get("message", "Backtest failed on resume"),
                }
            metrics = await asyncio.to_thread(parse_report, report_file)

        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "REPORT_PARSED",
            "completed",
            "Report parsed during resume",
            metrics,
        )

        backtest_result = _save_backtest_result(db, row.id, metrics, report_file)
        final_reviews, final_approval = await _run_review_cycle(
            db,
            strategy,
            metrics,
            "resume_review",
        )

        payload = {
            "status": "success",
            "strategy": strategy,
            "strategy_name": row.name,
            "strategy_id": row.id,
            "backtest_id": backtest_result.id,
            "timeframe": row.timeframe,
            "mql5_file": row.mql5_file,
            "config_file": config_path,
            "report_file": report_file,
            "metrics": metrics,
            "agent_reviews": final_reviews,
            "portfolio_decision": final_approval,
            "checkpoints": [cp.as_dict() for cp in list_checkpoints(db, strategy_name)],
        }
        await _checkpoint_and_broadcast(
            db,
            strategy_name,
            "DONE",
            "completed",
            "Pipeline resume completed successfully",
            payload,
        )
        return payload
    finally:
        db.close()
