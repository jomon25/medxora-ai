import json

from services.memory_store import recall_similar_memories


MAX_STOP_LOSS = 800
MIN_TAKE_PROFIT = 200
MAX_RISK_PERCENT = 2.0
MIN_REWARD_RATIO = 1.5
MAX_RSI_BUY = 68
MIN_RSI_SELL = 32


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class RiskManagerAgent:
    name = "Risk Manager Agent"

    def recall_similar_setups(self, db, strategy: dict, limit: int = 5) -> list[dict]:
        if db is None:
            return []

        recalls = recall_similar_memories(
            db,
            agent_name=self.name,
            strategy=strategy,
            category="decision",
            limit=limit,
        )
        items: list[dict] = []
        for item in recalls:
            row = item["row"]
            payload = item["payload"] or {}
            items.append({
                "strategy_name": row.strategy_name,
                "distance": item["distance"],
                "decision": payload.get("decision"),
                "actual_outcome": payload.get("actual_outcome"),
                "confidence": row.confidence,
                "memory_text": row.memory_text,
                "metrics": payload.get("metrics") or {},
            })
        return items

    def evaluate_memory_bias(self, db, strategy: dict) -> dict:
        memories = self.recall_similar_setups(db, strategy, limit=5)
        if not memories:
            return {
                "sample_size": 0,
                "failed_count": 0,
                "success_count": 0,
                "failure_rate": 0.0,
                "insight": "No similar setups in memory yet.",
                "should_block": False,
            }

        failed = [
            m for m in memories
            if m.get("actual_outcome") in {"unprofitable", "failed"}
        ]
        successful = [
            m for m in memories
            if m.get("actual_outcome") in {"profitable", "successful"}
        ]
        sample_size = len(memories)
        failure_rate = len(failed) / sample_size if sample_size else 0.0
        insight = (
            f"Memory recall: {len(failed)}/{sample_size} similar approved setups later failed."
            if failed else
            f"Memory recall: {len(successful)}/{sample_size} similar setups stayed profitable."
        )
        return {
            "sample_size": sample_size,
            "failed_count": len(failed),
            "success_count": len(successful),
            "failure_rate": round(failure_rate, 3),
            "insight": insight,
            "should_block": sample_size >= 4 and failure_rate >= 0.75,
            "memories": memories,
        }


def check_risk(strategy: dict, db=None, metrics: dict | None = None) -> dict:
    """
    Validate strategy parameters against risk rules and, when available,
    enrich the decision with memory from prior similar setups.
    """
    p = strategy.get("parameters", {})
    issues = []
    warnings = []

    sl = _to_float(p.get("stop_loss", 0))
    tp = _to_float(p.get("take_profit", 0))
    risk = _to_float(p.get("risk_percent", 0))
    fast = _to_float(p.get("fast_ema", 0))
    slow = _to_float(p.get("slow_ema", 0))
    rsi_buy = _to_float(p.get("rsi_buy", 55))
    rsi_sell = _to_float(p.get("rsi_sell", 45))

    if sl > MAX_STOP_LOSS:
        issues.append(f"Stop loss {sl:.0f} pts exceeds max {MAX_STOP_LOSS} pts")

    if tp < MIN_TAKE_PROFIT:
        issues.append(f"Take profit {tp:.0f} pts below min {MIN_TAKE_PROFIT} pts")

    if risk > MAX_RISK_PERCENT:
        issues.append(f"Risk {risk:.2f}% exceeds max {MAX_RISK_PERCENT}%")

    if sl > 0 and tp / sl < MIN_REWARD_RATIO:
        issues.append(f"Reward/Risk ratio {tp/sl:.2f} below min {MIN_REWARD_RATIO}")

    if fast >= slow:
        issues.append(f"Fast EMA {fast:.0f} must be less than Slow EMA {slow:.0f}")

    if rsi_buy > MAX_RSI_BUY:
        warnings.append(f"RSI buy level {rsi_buy:.1f} is very high (chasing momentum)")

    if rsi_sell < MIN_RSI_SELL:
        warnings.append(f"RSI sell level {rsi_sell:.1f} is very low (chasing momentum)")

    if slow - fast < 10:
        warnings.append(f"EMA gap {slow - fast:.0f} pts is narrow and may cause whipsaws")

    if metrics:
        drawdown = _to_float(metrics.get("max_drawdown", 0))
        if drawdown > 18:
            issues.append(f"Observed drawdown {drawdown:.1f}% is above the live-risk comfort zone")

    memory_summary = None
    if db is not None:
        memory_agent = RiskManagerAgent()
        memory_summary = memory_agent.evaluate_memory_bias(db, strategy)
        if memory_summary["sample_size"]:
            warnings.append(memory_summary["insight"])
        if memory_summary["should_block"]:
            issues.append(
                "Historical memory veto: similar setups were repeatedly approved but later underperformed."
            )

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "memory_summary": memory_summary,
    }


def check_strategy_risk(strategy: dict, db=None, metrics: dict | None = None) -> dict:
    """
    Compatibility helper for the final pipeline pack.
    Returns a simple status/message shape while preserving the richer checks.
    """
    result = check_risk(strategy, db=db, metrics=metrics)
    if result["passed"]:
        message = "Risk checks passed"
        if result["warnings"]:
            message = f"Risk checks passed with warnings: {result['warnings'][0]}"
        return {
            "status": "approved",
            "message": message,
            **result,
        }

    return {
        "status": "rejected",
        "message": "; ".join(result["issues"]),
        **result,
    }
