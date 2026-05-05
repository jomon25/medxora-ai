import json
import random
import uuid

from database.db import SessionLocal
from database.tables import OptimizationRun, Strategy
from services.batch_testing import (
    _best_entry,
    _build_entry,
    _entry_score,
    _evaluate_strategy,
    record_evolution_history,
    run_batch_test,
    summarize_batch_entries,
)
from services.logger import log_event
from services.mql5_generator import generate_mql5
from services.pipeline_ws import manager
from services.result_service import save_backtest_result
from services.strategy_filters import (
    run_post_backtest_filter,
    run_pre_backtest_filter,
    save_filter_result,
)
from services.strategy_service import save_strategy_to_db, update_strategy_mql5_file
from services.timeframes import normalize_timeframe


async def optimize_win_rate(
    target: float = 70,
    generations: int = 5,
    batch_size: int = 100,
    mock: bool = True,
    timeframe: str = "M15",
) -> dict:
    timeframe = normalize_timeframe(timeframe)
    await _broadcast(
        "OPTIMIZER_STARTED",
        "running",
        f"Win-rate optimization started for target {target}%",
        {"target": target, "generations": generations, "batch_size": batch_size, "mock": mock, "timeframe": timeframe},
    )

    initial_batch = await run_batch_test(count=batch_size, mock=mock, timeframe=timeframe, store_run=False)
    initial_win_rate = initial_batch.get("strategy_win_rate", 0)
    current_entries = [entry for entry in initial_batch.get("summary", []) if entry["status"] in {"qualified", "unqualified"}]
    best_entry = _best_entry(current_entries) or _best_entry(initial_batch.get("summary", []))

    history = [
        {
            "generation": 0,
            "tested": initial_batch.get("tested", 0),
            "profitable": initial_batch.get("profitable", 0),
            "win_rate": initial_win_rate,
            "best_strategy": best_entry,
        }
    ]
    best_win_rate = initial_win_rate

    for generation in range(1, generations + 1):
        elites = _select_elites(current_entries or initial_batch.get("summary", []))
        if not elites:
            break

        generation_entries = []
        for elite in elites:
            children_per_elite = 3 if len(elites) >= 10 else 5
            for _ in range(children_per_elite):
                child_strategy = _mutate_child(elite["strategy"], elite)
                child_id = save_strategy_to_db(
                    child_strategy,
                    parent_id=elite["strategy_id"],
                    generation=(elite.get("generation") or 0) + 1,
                )
                pre_filter = run_pre_backtest_filter(child_strategy)
                save_filter_result(child_id, pre_filter, "pre")
                if not pre_filter["approved"]:
                    generation_entries.append(
                        _build_entry(
                            strategy_id=child_id,
                            strategy=child_strategy,
                            status="rejected",
                            mode="mock" if mock else "real",
                            pre_filter=pre_filter,
                            reason="; ".join(pre_filter["reasons"]),
                        )
                    )
                    record_evolution_history(
                        elite["strategy_id"],
                        child_id,
                        _mutation_details(elite["strategy"], child_strategy),
                        elite.get("score", 0),
                        0,
                        False,
                    )
                    continue

                try:
                    file_path = generate_mql5(child_strategy)
                    update_strategy_mql5_file(child_id, file_path)
                    evaluation = _evaluate_strategy(child_strategy, mock=mock)
                except Exception as exc:
                    generation_entries.append(
                        _build_entry(
                            strategy_id=child_id,
                            strategy=child_strategy,
                            status="failed",
                            mode="mock" if mock else "real",
                            pre_filter=pre_filter,
                            reason=str(exc),
                        )
                    )
                    record_evolution_history(
                        elite["strategy_id"],
                        child_id,
                        _mutation_details(elite["strategy"], child_strategy),
                        elite.get("score", 0),
                        0,
                        False,
                    )
                    continue

                if evaluation["status"] != "success":
                    generation_entries.append(
                        _build_entry(
                            strategy_id=child_id,
                            strategy=child_strategy,
                            status="failed",
                            mode="mock" if mock else "real",
                            pre_filter=pre_filter,
                            reason=evaluation.get("message", "Backtest failed"),
                        )
                    )
                    record_evolution_history(
                        elite["strategy_id"],
                        child_id,
                        _mutation_details(elite["strategy"], child_strategy),
                        elite.get("score", 0),
                        0,
                        False,
                    )
                    continue

                metrics = evaluation["metrics"]
                metrics["status"] = "completed"
                metrics["report_file"] = evaluation.get("report_file")
                result_id = save_backtest_result(child_id, metrics)
                post_filter = run_post_backtest_filter(metrics)
                save_filter_result(child_id, post_filter, "post")
                child_score = _entry_score(metrics)
                improved = child_score > elite.get("score", 0)

                generation_entries.append(
                    _build_entry(
                        strategy_id=child_id,
                        result_id=result_id,
                        strategy=child_strategy,
                        status="qualified" if post_filter["approved"] else "unqualified",
                        mode="mock" if mock else "real",
                        pre_filter=pre_filter,
                        post_filter=post_filter,
                        metrics=metrics,
                        mql5_file=file_path,
                    )
                )
                record_evolution_history(
                    elite["strategy_id"],
                    child_id,
                    _mutation_details(elite["strategy"], child_strategy),
                    elite.get("score", 0),
                    child_score,
                    improved,
                )

        generation_summary = summarize_batch_entries(generation_entries, requested_count=len(generation_entries))
        generation_best = _best_entry(generation_entries)
        history.append(
            {
                "generation": generation,
                "tested": len(generation_entries),
                "profitable": generation_summary.get("profitable", 0),
                "win_rate": generation_summary.get("strategy_win_rate", 0),
                "best_strategy": generation_best,
            }
        )

        current_entries = [entry for entry in generation_entries if entry["status"] == "qualified"]
        if generation_summary.get("strategy_win_rate", 0) > best_win_rate:
            best_win_rate = generation_summary["strategy_win_rate"]
            best_entry = generation_best or best_entry

        await _broadcast(
            "OPTIMIZER_PROGRESS",
            "running" if generation < generations and best_win_rate < target else "completed",
            f"Optimization generation {generation} reached {generation_summary.get('strategy_win_rate', 0)}% win rate",
            {
                "generation": generation,
                "tested": len(generation_entries),
                "profitable": generation_summary.get("profitable", 0),
                "win_rate": generation_summary.get("strategy_win_rate", 0),
            },
        )
        if best_win_rate >= target:
            break

    final_win_rate = round(best_win_rate, 2)
    improvement = round(final_win_rate - initial_win_rate, 2)
    optimization = {
        "status": "success",
        "target_win_rate": target,
        "initial_win_rate": round(initial_win_rate, 2),
        "final_win_rate": final_win_rate,
        "generations": len(history) - 1,
        "best_strategy": best_entry,
        "improvement": f"{improvement:+.2f}%",
        "generation_history": history,
        "mode": "mock" if mock else "real",
        "batch_size": batch_size,
    }
    optimization["optimization_run_id"] = _save_optimization_run(optimization)

    await _broadcast(
        "OPTIMIZER_COMPLETED",
        "completed",
        f"Win-rate optimization completed at {final_win_rate}%",
        {
            "target": target,
            "final_win_rate": final_win_rate,
            "improvement": optimization["improvement"],
        },
    )
    log_event("INFO", f"Optimization target reached: {final_win_rate}%", source="win_rate_optimizer")
    return optimization


def _select_elites(entries: list[dict]) -> list[dict]:
    ranked = [entry for entry in entries if entry["status"] in {"qualified", "unqualified"}]
    if not ranked:
        ranked = entries
    ranked = sorted(ranked, key=lambda entry: entry.get("score", 0), reverse=True)
    elite_count = max(1, int(len(ranked) * 0.2))
    return ranked[:elite_count]


def _mutate_child(strategy: dict, parent_entry: dict) -> dict:
    params = dict(strategy.get("parameters", {}))
    reward_risk = (params.get("take_profit", 400) / max(params.get("stop_loss", 1), 1))
    bias_up = parent_entry.get("win_rate", 0) >= 60

    params["fast_ema"] = _clamp(params.get("fast_ema", 15) + random.randint(-2, 2), 6, 35)
    params["slow_ema"] = _clamp(max(params["fast_ema"] + 10, params.get("slow_ema", 55) + random.randint(-6, 8)), 25, 120)
    params["rsi_buy"] = _clamp(params.get("rsi_buy", 58) + random.randint(-1, 3), 52, 68)
    params["rsi_sell"] = _clamp(params.get("rsi_sell", 42) + random.randint(-3, 1), 32, 48)
    params["stop_loss"] = _clamp(params.get("stop_loss", 320) + random.randint(-40, 35), 150, 650)

    if reward_risk < 1.7 or not bias_up:
        take_profit_base = int(params["stop_loss"] * random.uniform(1.65, 2.25))
    else:
        take_profit_base = int(params.get("take_profit", 600) + random.randint(-60, 120))
    params["take_profit"] = _clamp(max(take_profit_base, int(params["stop_loss"] * 1.6)), 260, 2800)
    params["risk_percent"] = round(_clamp(float(params.get("risk_percent", 1.0)) + random.uniform(-0.1, 0.15), 0.5, 2.0), 2)

    return {
        **strategy,
        "name": f"EMA_RSI_{uuid.uuid4().hex[:8].upper()}",
        "generation": (strategy.get("generation") or 0) + 1,
        "parameters": params,
    }


def _mutation_details(parent: dict, child: dict) -> dict:
    details = {}
    parent_params = parent.get("parameters", {})
    child_params = child.get("parameters", {})
    for key, parent_value in parent_params.items():
        child_value = child_params.get(key)
        if child_value != parent_value:
            details[key] = {"from": parent_value, "to": child_value}
    return details


def _save_optimization_run(result: dict) -> int:
    db = SessionLocal()
    try:
        best_strategy_id = result.get("best_strategy", {}).get("strategy_id")
        row = OptimizationRun(
            target_win_rate=result.get("target_win_rate"),
            initial_win_rate=result.get("initial_win_rate"),
            final_win_rate=result.get("final_win_rate"),
            generations=result.get("generations", 0),
            best_strategy_id=best_strategy_id,
            mode=result.get("mode", "mock"),
            batch_size=result.get("batch_size", 0),
            improvement=result.get("improvement"),
            history_json=json.dumps(result.get("generation_history", [])),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _clamp(value, low, high):
    return max(low, min(value, high))


async def _broadcast(stage: str, status: str, message: str, data=None) -> None:
    level = "ERROR" if status in {"failed", "error"} else "INFO"
    log_event(level, f"{stage} | {message}", source="win_rate_optimizer")
    await manager.broadcast(stage, status, message, data or {})
