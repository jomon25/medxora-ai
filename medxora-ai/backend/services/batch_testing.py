import hashlib
import json
import random
from statistics import mean

from agents.strategy_creator import generate_strategy
from database.db import SessionLocal
from database.tables import (
    BacktestResult,
    BatchRun,
    EvolutionHistory,
    OptimizationRun,
    Strategy,
)
from services.logger import log_event
from services.mql5_generator import generate_mql5
from services.mt5_config_generator import run_backtest
from services.pipeline_ws import manager
from services.report_parser import parse_report
from services.result_service import save_backtest_result
from services.strategy_filters import (
    run_post_backtest_filter,
    run_pre_backtest_filter,
    save_filter_result,
)
from services.strategy_service import save_strategy_to_db, update_strategy_mql5_file
from services.timeframes import normalize_timeframe


async def run_batch_test(
    count: int = 100,
    mock: bool = True,
    timeframe: str = "M15",
    store_run: bool = True,
) -> dict:
    timeframe = normalize_timeframe(timeframe)
    summary = []
    profitable = 0
    rejected = 0
    failed = 0

    await _broadcast(
        "BATCH_STARTED",
        "running",
        f"Batch testing started for {count} strategies",
        {"count": count, "mock": mock, "timeframe": timeframe},
    )

    for index in range(count):
        strategy = generate_strategy(timeframe)
        strategy_id = save_strategy_to_db(strategy)
        log_event("INFO", f"Batch strategy generated: {strategy['name']}", source="batch_testing")

        pre_filter = run_pre_backtest_filter(strategy)
        save_filter_result(strategy_id, pre_filter, "pre")

        if not pre_filter["approved"]:
            rejected += 1
            entry = _build_entry(
                strategy_id=strategy_id,
                strategy=strategy,
                status="rejected",
                mode="mock" if mock else "real",
                pre_filter=pre_filter,
                reason="; ".join(pre_filter["reasons"]),
            )
            summary.append(entry)
            await _broadcast(
                "BATCH_FILTER_REJECTED",
                "completed",
                f"{strategy['name']} rejected by pre-filter",
                {"index": index + 1, "count": count, "strategy": strategy["name"], "reasons": pre_filter["reasons"]},
            )
            continue

        try:
            mql5_file = generate_mql5(strategy)
            update_strategy_mql5_file(strategy_id, mql5_file)
            evaluation = _evaluate_strategy(strategy, mock=mock)
        except Exception as exc:
            failed += 1
            log_event("ERROR", f"Batch execution failed for {strategy['name']}: {exc}", source="batch_testing")
            entry = _build_entry(
                strategy_id=strategy_id,
                strategy=strategy,
                status="failed",
                mode="mock" if mock else "real",
                pre_filter=pre_filter,
                reason=str(exc),
            )
            summary.append(entry)
            await _broadcast(
                "BATCH_FAILED",
                "failed",
                f"{strategy['name']} failed during testing",
                {"index": index + 1, "count": count, "strategy": strategy["name"], "error": str(exc)},
            )
            continue

        if evaluation["status"] != "success":
            failed += 1
            entry = _build_entry(
                strategy_id=strategy_id,
                strategy=strategy,
                status="failed",
                mode="mock" if mock else "real",
                pre_filter=pre_filter,
                reason=evaluation.get("message", "Backtest failed"),
                mql5_file=mql5_file,
            )
            summary.append(entry)
            await _broadcast(
                "BATCH_FAILED",
                "failed",
                f"{strategy['name']} backtest failed",
                {"index": index + 1, "count": count, "strategy": strategy["name"], "error": evaluation.get("message")},
            )
            continue

        metrics = evaluation["metrics"]
        metrics["status"] = "completed"
        metrics["report_file"] = evaluation.get("report_file")
        result_id = save_backtest_result(strategy_id, metrics)
        post_filter = run_post_backtest_filter(metrics)
        save_filter_result(strategy_id, post_filter, "post")

        status = "qualified" if post_filter["approved"] else "unqualified"
        if post_filter["approved"]:
            profitable += 1

        entry = _build_entry(
            strategy_id=strategy_id,
            strategy=strategy,
            status=status,
            mode="mock" if mock else "real",
            pre_filter=pre_filter,
            post_filter=post_filter,
            metrics=metrics,
            mql5_file=mql5_file,
            result_id=result_id,
        )
        summary.append(entry)
        await _broadcast(
            "BATCH_PROGRESS",
            "running" if index + 1 < count else "completed",
            f"Batch tested {index + 1}/{count} strategies",
            {
                "index": index + 1,
                "count": count,
                "strategy": strategy["name"],
                "qualified": post_filter["approved"],
                "net_profit": metrics.get("net_profit"),
                "win_rate": metrics.get("win_rate"),
            },
        )

    aggregate = summarize_batch_entries(summary, requested_count=count)
    aggregate["status"] = "success"
    aggregate["count"] = count
    aggregate["tested"] = count
    aggregate["profitable"] = profitable
    aggregate["rejected_by_filter"] = rejected
    aggregate["failed"] = failed
    aggregate["summary"] = summary
    aggregate["mode"] = "mock" if mock else "real"
    aggregate["timeframe"] = timeframe

    if store_run:
        aggregate["batch_run_id"] = save_batch_run(aggregate)

    await _broadcast(
        "BATCH_COMPLETED",
        "completed",
        f"Batch testing completed with {profitable} profitable strategies",
        {
            "count": count,
            "profitable": profitable,
            "rejected": rejected,
            "failed": failed,
            "strategy_win_rate": aggregate["strategy_win_rate"],
        },
    )
    return aggregate


def summarize_batch_entries(summary: list[dict], requested_count: int | None = None) -> dict:
    completed = [entry for entry in summary if entry["status"] in {"qualified", "unqualified"}]
    profitable_entries = [entry for entry in summary if entry["status"] == "qualified"]
    rejected_entries = [entry for entry in summary if entry["status"] == "rejected"]
    failed_entries = [entry for entry in summary if entry["status"] == "failed"]
    losing = len(completed) - len(profitable_entries)

    profit_factors = [entry["profit_factor"] for entry in completed if entry.get("profit_factor") is not None]
    drawdowns = [entry["max_drawdown"] for entry in completed if entry.get("max_drawdown") is not None]

    best_strategy = _best_entry(completed)
    worst_strategy = _worst_entry(completed)
    denominator = requested_count or len(summary) or 1

    return {
        "tested": requested_count or len(summary),
        "completed": len(completed),
        "profitable": len(profitable_entries),
        "losing": losing,
        "rejected_by_filter": len(rejected_entries),
        "failed": len(failed_entries),
        "strategy_win_rate": round((len(profitable_entries) / denominator) * 100, 2),
        "average_profit_factor": round(mean(profit_factors), 2) if profit_factors else 0,
        "average_drawdown": round(mean(drawdowns), 2) if drawdowns else 0,
        "best_strategy": best_strategy,
        "worst_strategy": worst_strategy,
    }


def save_batch_run(aggregate: dict) -> int:
    db = SessionLocal()
    try:
        best_strategy_id = aggregate.get("best_strategy", {}).get("strategy_id")
        row = BatchRun(
            count=aggregate.get("count", 0),
            tested=aggregate.get("tested", 0),
            profitable=aggregate.get("profitable", 0),
            losing=aggregate.get("losing", 0),
            rejected=aggregate.get("rejected_by_filter", 0),
            failed=aggregate.get("failed", 0),
            win_rate=aggregate.get("strategy_win_rate"),
            avg_profit_factor=aggregate.get("average_profit_factor"),
            avg_drawdown=aggregate.get("average_drawdown"),
            best_strategy_id=best_strategy_id,
            mode=aggregate.get("mode", "mock"),
            summary_json=json.dumps(aggregate.get("summary", [])),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def get_latest_batch() -> dict:
    db = SessionLocal()
    try:
        row = db.query(BatchRun).order_by(BatchRun.created_at.desc()).first()
        if row is None:
            return {
                "status": "success",
                "count": 0,
                "tested": 0,
                "profitable": 0,
                "losing": 0,
                "rejected_by_filter": 0,
                "failed": 0,
                "strategy_win_rate": 0,
                "average_profit_factor": 0,
                "average_drawdown": 0,
                "best_strategy": None,
                "worst_strategy": None,
                "summary": [],
            }

        data = row.as_dict()
        summary = data.get("summary", [])
        data["status"] = "success"
        data["rejected_by_filter"] = data.pop("rejected", 0)
        data["strategy_win_rate"] = data.pop("win_rate", 0)
        data["average_profit_factor"] = data.pop("avg_profit_factor", 0)
        data["average_drawdown"] = data.pop("avg_drawdown", 0)
        data["best_strategy"] = _best_entry(summary)
        data["worst_strategy"] = _worst_entry(summary)
        return data
    finally:
        db.close()


def get_win_rate_stats() -> dict:
    db = SessionLocal()
    try:
        latest_batch = get_latest_batch()
        if latest_batch.get("summary"):
            profitable = latest_batch.get("profitable", 0)
            losing = latest_batch.get("losing", 0)
            rejected = latest_batch.get("rejected_by_filter", 0)
            failed = latest_batch.get("failed", 0)
            win_rate = latest_batch.get("strategy_win_rate", 0)
            avg_profit_factor = latest_batch.get("average_profit_factor", 0)
            avg_drawdown = latest_batch.get("average_drawdown", 0)
            best_strategy = latest_batch.get("best_strategy")
            worst_strategy = latest_batch.get("worst_strategy")
            total_tested = latest_batch.get("tested", 0)
            batch_summary = latest_batch.get("summary", [])
        else:
            results = db.query(BacktestResult).all()
            total_tested = len(results)
            profitable_rows = [row for row in results if (row.net_profit or 0) > 0]
            losing_rows = [row for row in results if (row.net_profit or 0) <= 0]
            profitable = len(profitable_rows)
            losing = len(losing_rows)
            rejected = db.query(Strategy).count() - total_tested
            failed = 0
            win_rate = round((profitable / total_tested) * 100, 2) if total_tested else 0
            avg_profit_factor = round(mean([row.profit_factor for row in results if row.profit_factor is not None]), 2) if results else 0
            avg_drawdown = round(mean([row.max_drawdown for row in results if row.max_drawdown is not None]), 2) if results else 0
            best_strategy = _serialize_result_row(max(results, key=lambda row: row.net_profit or float("-inf"))) if results else None
            worst_strategy = _serialize_result_row(min(results, key=lambda row: row.net_profit or float("inf"))) if results else None
            batch_summary = []

        real_mt5_runs = (
            db.query(BacktestResult)
            .filter(BacktestResult.report_file.isnot(None))
            .filter(BacktestResult.report_file != "")
            .count()
        )

        evolution_rows = db.query(EvolutionHistory).all()
        evolution_success_rate = (
            round((sum(1 for row in evolution_rows if str(row.improved).lower() == "true") / len(evolution_rows)) * 100, 2)
            if evolution_rows else 0
        )

        latest_optimization_row = db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc()).first()
        latest_optimization = latest_optimization_row.as_dict() if latest_optimization_row else None

        return {
            "status": "success",
            "tested": total_tested,
            "profitable_count": profitable,
            "losing_count": losing,
            "rejected_by_filter": rejected,
            "failed": failed,
            "strategy_win_rate": win_rate,
            "average_profit_factor": avg_profit_factor,
            "average_drawdown": avg_drawdown,
            "best_strategy": best_strategy,
            "worst_strategy": worst_strategy,
            "evolution_success_rate": evolution_success_rate,
            "real_mt5_runs": real_mt5_runs,
            "latest_batch": latest_batch,
            "latest_optimization": latest_optimization,
            "batch_summary": batch_summary,
            "demo_metrics": {
                "before_evolution": {
                    "tested_strategies": latest_batch.get("tested", 0),
                    "profitable": latest_batch.get("profitable", 0),
                    "win_rate": latest_batch.get("strategy_win_rate", 0),
                },
                "after_evolution": {
                    "tested_strategies": latest_optimization.get("batch_size", latest_batch.get("tested", 0)) if latest_optimization else latest_batch.get("tested", 0),
                    "profitable": round((latest_optimization.get("final_win_rate", 0) / 100) * latest_optimization.get("batch_size", 0)) if latest_optimization else latest_batch.get("profitable", 0),
                    "win_rate": latest_optimization.get("final_win_rate", latest_batch.get("strategy_win_rate", 0)) if latest_optimization else latest_batch.get("strategy_win_rate", 0),
                    "avg_drawdown": latest_batch.get("average_drawdown", 0),
                    "avg_profit_factor": latest_batch.get("average_profit_factor", 0),
                },
            },
        }
    finally:
        db.close()


def record_evolution_history(
    parent_strategy_id: int,
    child_strategy_id: int,
    mutation_details: dict,
    parent_score: float,
    child_score: float,
    improved: bool,
) -> None:
    db = SessionLocal()
    try:
        row = EvolutionHistory(
            parent_strategy_id=parent_strategy_id,
            child_strategy_id=child_strategy_id,
            mutation_details_json=json.dumps(mutation_details),
            parent_score=parent_score,
            child_score=child_score,
            improved="true" if improved else "false",
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _evaluate_strategy(strategy: dict, mock: bool) -> dict:
    if mock:
        return {
            "status": "success",
            "report_file": None,
            "metrics": _mock_metrics_from_strategy(strategy),
        }

    run_result = run_backtest(strategy["name"])
    if run_result.get("status") != "success":
        return run_result

    report_file = run_result.get("report_file")
    metrics = parse_report(report_file)
    return {
        "status": "success",
        "report_file": report_file,
        "metrics": metrics,
    }


def _mock_metrics_from_strategy(strategy: dict) -> dict:
    params = strategy.get("parameters", {})
    fast_ema = float(params.get("fast_ema", 10) or 10)
    slow_ema = float(params.get("slow_ema", 40) or 40)
    stop_loss = float(params.get("stop_loss", 250) or 250)
    take_profit = float(params.get("take_profit", 450) or 450)
    rsi_buy = float(params.get("rsi_buy", 58) or 58)
    rsi_sell = float(params.get("rsi_sell", 42) or 42)
    timeframe = strategy.get("timeframe", "M15")

    seed_source = json.dumps([strategy.get("name"), params, timeframe], sort_keys=True)
    seed = int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    reward_risk = take_profit / stop_loss if stop_loss > 0 else 0
    ema_gap = slow_ema - fast_ema
    rsi_gap = rsi_buy - rsi_sell

    timeframe_bonus = {"M1": -4, "M15": 2, "H1": 4, "H4": 3, "D1": 1, "W1": -1}.get(timeframe, 0)
    win_rate = (
        46
        + min(max((reward_risk - 1.0) * 12, -8), 14)
        + min(max((ema_gap - 20) * 0.18, -6), 8)
        + min(max((rsi_gap - 10) * 0.9, -8), 10)
        + timeframe_bonus
        + rng.uniform(-4.5, 4.5)
    )
    win_rate = round(min(max(win_rate, 32), 84), 2)

    total_trades = max(24, int(90 + ema_gap * 2 + rng.randint(-30, 70)))
    drawdown = round(
        min(
            max(
                14.5
                - (reward_risk - 1.2) * 4.5
                - (rsi_gap - 10) * 0.15
                - timeframe_bonus * 0.5
                + rng.uniform(-1.8, 2.4),
                3.2,
            ),
            24.0,
        ),
        2,
    )
    profit_factor = round(
        min(
            max(
                0.85
                + (win_rate - 45) * 0.025
                + (reward_risk - 1.0) * 0.35
                - max(drawdown - 10, 0) * 0.02
                + rng.uniform(-0.08, 0.12),
                0.75,
            ),
            2.9,
        ),
        2,
    )
    sharpe_ratio = round(
        min(
            max(
                0.25
                + (profit_factor - 1.0) * 0.8
                + (win_rate - 50) * 0.015
                - drawdown * 0.015
                + rng.uniform(-0.08, 0.12),
                0.05,
            ),
            2.7,
        ),
        2,
    )
    robustness_score = _robustness_score(reward_risk, drawdown, total_trades)
    expected_payoff = round(
        ((win_rate / 100) * take_profit) - (((100 - win_rate) / 100) * stop_loss),
        2,
    )
    net_profit = round(
        (expected_payoff * total_trades * 0.55)
        + (profit_factor * 420)
        - (drawdown * 55)
        + robustness_score * 8
        + rng.uniform(-180, 220),
        2,
    )
    gross_profit = round(max(net_profit, 0) * (1 + profit_factor / 2), 2)
    gross_loss = round(max(gross_profit - net_profit, 0), 2)
    recovery_factor = round(max(net_profit / max(drawdown * 100, 1), 0.1), 2)

    return {
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "max_drawdown": drawdown,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "profit_factor": profit_factor,
        "expected_payoff": expected_payoff,
        "sharpe_ratio": sharpe_ratio,
        "recovery_factor": recovery_factor,
        "monthly_profit": round(net_profit / 12, 2),
        "yearly_profit": round(net_profit, 2),
        "robustness_score": robustness_score,
    }


def _robustness_score(reward_risk: float, drawdown: float, total_trades: int) -> float:
    trade_score = min(total_trades / 10, 25)
    rr_score = max((reward_risk - 1.0) * 12, 0)
    dd_score = max(18 - drawdown, 0)
    return round(trade_score + rr_score + dd_score, 2)


def _build_entry(
    strategy_id: int,
    strategy: dict,
    status: str,
    mode: str,
    pre_filter: dict | None = None,
    post_filter: dict | None = None,
    metrics: dict | None = None,
    mql5_file: str | None = None,
    result_id: int | None = None,
    reason: str | None = None,
) -> dict:
    metrics = metrics or {}
    return {
        "strategy_id": strategy_id,
        "result_id": result_id,
        "name": strategy.get("name"),
        "symbol": strategy.get("symbol", "EURUSD"),
        "timeframe": strategy.get("timeframe", "M15"),
        "generation": strategy.get("generation", 0),
        "status": status,
        "mode": mode,
        "net_profit": metrics.get("net_profit"),
        "profit_factor": metrics.get("profit_factor"),
        "max_drawdown": metrics.get("max_drawdown"),
        "win_rate": metrics.get("win_rate"),
        "total_trades": metrics.get("total_trades"),
        "qualified": status == "qualified",
        "mql5_file": mql5_file,
        "pre_filter": pre_filter,
        "post_filter": post_filter,
        "reason": reason,
        "strategy": strategy,
        "metrics": metrics,
        "score": _entry_score(metrics),
    }


def _entry_score(metrics: dict | None) -> float:
    if not metrics:
        return 0
    return round(
        (float(metrics.get("net_profit", 0) or 0) * 0.30)
        + (float(metrics.get("profit_factor", 0) or 0) * 250)
        + (float(metrics.get("win_rate", 0) or 0) * 4)
        + (float(metrics.get("sharpe_ratio", 0) or 0) * 150)
        - (float(metrics.get("max_drawdown", 0) or 0) * 20)
        + (float(metrics.get("robustness_score", 0) or 0) * 2),
        2,
    )


def _best_entry(entries: list[dict]) -> dict | None:
    if not entries:
        return None
    return max(entries, key=lambda entry: (entry.get("net_profit") if entry.get("net_profit") is not None else float("-inf")))


def _worst_entry(entries: list[dict]) -> dict | None:
    if not entries:
        return None
    return min(entries, key=lambda entry: (entry.get("net_profit") if entry.get("net_profit") is not None else float("inf")))


def _serialize_result_row(row: BacktestResult) -> dict:
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter(Strategy.id == row.strategy_id).first()
        return {
            "strategy_id": row.strategy_id,
            "name": strategy.name if strategy else f"Strategy {row.strategy_id}",
            "net_profit": row.net_profit,
            "profit_factor": row.profit_factor,
            "max_drawdown": row.max_drawdown,
            "win_rate": row.win_rate,
            "total_trades": row.total_trades,
            "status": row.status,
        }
    finally:
        db.close()


async def _broadcast(stage: str, status: str, message: str, data=None) -> None:
    level = "ERROR" if status in {"failed", "error"} else "INFO"
    log_event(level, f"{stage} | {message}", source="batch_testing")
    await manager.broadcast(stage, status, message, data or {})
