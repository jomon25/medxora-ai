import math

_PARAM_KEYS = [
    "fast_ema", "slow_ema", "rsi_period", "rsi_buy", "rsi_sell",
    "stop_loss", "take_profit", "risk_percent",
    "bb_period", "bb_deviation", "macd_fast", "macd_slow", "macd_signal",
    "atr_period", "atr_multiplier", "adx_period", "adx_threshold",
    "donchian_period", "breakout_period",
]

_SCALE = {
    "fast_ema": 50, "slow_ema": 100, "rsi_period": 28, "rsi_buy": 100,
    "rsi_sell": 100, "stop_loss": 800, "take_profit": 1200, "risk_percent": 2.0,
    "bb_period": 50, "bb_deviation": 5.0, "macd_fast": 20, "macd_slow": 35,
    "macd_signal": 15, "atr_period": 28, "atr_multiplier": 5.0,
    "adx_period": 30, "adx_threshold": 50, "donchian_period": 50, "breakout_period": 50,
}


def _fingerprint(strategy: dict) -> list[float]:
    p = strategy.get("parameters", {})
    return [float(p.get(k, 0) or 0) / _SCALE.get(k, 1) for k in _PARAM_KEYS]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b) if mag_a > 0 and mag_b > 0 else 0.0


def _pearson_corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(b) < 3:
        return None
    size = min(len(a), len(b))
    xs = a[:size]
    ys = b[:size]
    mean_x = sum(xs) / size
    mean_y = sum(ys) / size
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _metric_series(strategy: dict) -> list[float]:
    if strategy.get("return_series"):
        return [float(v) for v in strategy.get("return_series", []) if v is not None]

    metrics = strategy.get("metrics_history") or []
    series = []
    for row in metrics:
        net_profit = float(row.get("net_profit", 0) or 0)
        monthly_profit = float(row.get("monthly_profit", 0) or 0)
        profit_factor = float(row.get("profit_factor", 1.0) or 1.0)
        series.append(round(net_profit * 0.001 + monthly_profit * 0.02 + profit_factor, 4))
    return series


def run_correlation_guard_agent(strategy: dict, existing_strategies: list[dict] | None = None) -> dict:
    if not existing_strategies:
        return {
            "agent": "Correlation Guard Agent",
            "decision": "approve",
            "confidence": 0.75,
            "risk_level": "low",
            "reason": "Portfolio is empty, so there is no portfolio correlation risk yet.",
            "evidence": ["No existing strategies to compare against."],
            "data": {"max_correlation": 0.0, "correlations": [], "is_duplicate": False},
            "review_state": "Approved",
        }

    fp = _fingerprint(strategy)
    candidate_series = _metric_series(strategy)
    stype = strategy.get("strategy_type", "")
    correlations = []

    for ex in existing_strategies:
        if ex.get("name") == strategy.get("name"):
            continue

        ex_series = _metric_series(ex)
        return_corr = _pearson_corr(candidate_series, ex_series)
        similarity = _cosine_sim(fp, _fingerprint(ex))
        same_type = ex.get("strategy_type") == stype

        effective_corr = abs(return_corr) if return_corr is not None else similarity
        method = "return_correlation" if return_corr is not None else "parameter_similarity"
        correlations.append({
            "name": ex.get("name", "unknown"),
            "correlation": round(effective_corr, 4),
            "raw_return_correlation": round(return_corr, 4) if return_corr is not None else None,
            "parameter_similarity": round(similarity, 4),
            "same_type": same_type,
            "method": method,
            "is_duplicate": similarity > 0.95 and same_type,
        })

    if not correlations:
        max_corr, is_duplicate = 0.0, False
    else:
        max_corr = max(c["correlation"] for c in correlations)
        is_duplicate = any(c["is_duplicate"] for c in correlations)

    high_corr = [c for c in correlations if c["correlation"] > 0.60]
    top_match = sorted(correlations, key=lambda x: x["correlation"], reverse=True)
    using_return_corr = any(c["method"] == "return_correlation" for c in correlations)

    evidence = [
        f"Compared against {len(correlations)} portfolio strategies",
        f"Max effective correlation: {max_corr:.3f}",
        f"High correlation breaches (>0.60): {len(high_corr)}",
        f"Correlation method: {'actual return history when available, parameter fallback otherwise' if using_return_corr else 'parameter fallback only'}",
        f"Exact duplicate: {is_duplicate}",
    ]
    if top_match:
        evidence.append(
            f"Closest match: '{top_match[0]['name']}' at {top_match[0]['correlation']*100:.1f}% correlation"
        )

    if is_duplicate or max_corr > 0.90:
        return {
            "agent": "Correlation Guard Agent",
            "decision": "reject",
            "confidence": 0.93,
            "risk_level": "high",
            "reason": "This strategy is too correlated with an existing live candidate and adds little diversification value.",
            "evidence": evidence,
            "data": {"max_correlation": round(max_corr, 4), "correlations": top_match[:5], "is_duplicate": True},
            "review_state": "Rejected",
        }

    if max_corr > 0.60 or len(high_corr) >= 2:
        decision, confidence, risk_level, review_state = "needs_evolution", 0.80, "medium", "Needs Evolution"
        reason = f"Portfolio correlation is above the 0.60 live threshold (max {max_corr:.0%}). Adjust parameters before admission."
    elif max_corr > 0.45:
        decision, confidence, risk_level, review_state = "needs_retest", 0.72, "medium", "Needs Retest"
        reason = f"Correlation is moderate at {max_corr:.0%}. Retest with additional data before live deployment."
    else:
        decision, confidence, risk_level, review_state = "approve", round(min(0.80 + (1.0 - max_corr) * 0.15, 0.95), 3), "low", "Approved"
        reason = f"Strategy remains diversified enough for the live portfolio (max correlation {max_corr:.0%})."

    return {
        "agent": "Correlation Guard Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "max_correlation": round(max_corr, 4),
            "correlations": top_match[:5],
            "high_correlation_count": len(high_corr),
            "used_return_correlation": using_return_corr,
            "is_duplicate": False,
        },
        "review_state": review_state,
    }
