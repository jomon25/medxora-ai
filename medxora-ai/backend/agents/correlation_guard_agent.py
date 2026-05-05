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
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b) if mag_a > 0 and mag_b > 0 else 0.0


def run_correlation_guard_agent(strategy: dict, existing_strategies: list[dict] | None = None) -> dict:
    if not existing_strategies:
        return {
            "agent": "Correlation Guard Agent",
            "decision": "approve",
            "confidence": 0.75,
            "risk_level": "low",
            "reason": "Portfolio is empty — no correlation risk. Strategy accepted as first entry.",
            "evidence": ["No existing strategies to compare against."],
            "data": {"max_correlation": 0.0, "correlations": [], "is_duplicate": False},
            "review_state": "Approved",
        }

    fp = _fingerprint(strategy)
    stype = strategy.get("strategy_type", "")

    correlations = []
    for ex in existing_strategies:
        if ex.get("name") == strategy.get("name"):
            continue
        sim = _cosine_sim(fp, _fingerprint(ex))
        same_type = ex.get("strategy_type") == stype
        correlations.append({
            "name": ex.get("name", "unknown"),
            "similarity": round(sim, 4),
            "same_type": same_type,
            "is_duplicate": sim > 0.95 and same_type,
        })

    if not correlations:
        max_sim, is_duplicate = 0.0, False
    else:
        max_sim     = max(c["similarity"] for c in correlations)
        is_duplicate = any(c["is_duplicate"] for c in correlations)

    high_corr = [c for c in correlations if c["similarity"] > 0.80]
    top_match = sorted(correlations, key=lambda x: x["similarity"], reverse=True)

    evidence = [
        f"Compared against {len(correlations)} portfolio strategies",
        f"Max similarity score: {max_sim:.3f} (1.0 = identical)",
        f"Highly correlated (>80%): {len(high_corr)} strategies",
        f"Exact duplicate: {is_duplicate}",
    ]
    if top_match:
        evidence.append(f"Most similar: '{top_match[0]['name']}' ({top_match[0]['similarity']*100:.1f}% similar)")

    if is_duplicate or max_sim > 0.95:
        return {
            "agent": "Correlation Guard Agent",
            "decision": "reject",
            "confidence": 0.93,
            "risk_level": "high",
            "reason": "Near-identical strategy already in portfolio. Adding it does not improve diversification.",
            "evidence": evidence,
            "data": {"max_correlation": round(max_sim, 4), "correlations": top_match[:5], "is_duplicate": True},
            "review_state": "Rejected",
        }

    if max_sim > 0.80 or len(high_corr) >= 2:
        decision, confidence, risk_level, review_state = "needs_evolution", 0.78, "medium", "Needs Evolution"
        reason = f"High correlation ({max_sim:.0%}) with existing strategies. Evolution toward new parameters improves diversification."
    elif max_sim > 0.65:
        decision, confidence, risk_level, review_state = "needs_retest", 0.70, "medium", "Needs Retest"
        reason = f"Moderate correlation ({max_sim:.0%}). Acceptable if performance profile is distinct."
    else:
        decision, confidence, risk_level, review_state = "approve", round(min(0.80 + (1.0 - max_sim) * 0.15, 0.95), 3), "low", "Approved"
        reason = f"Strategy is sufficiently unique (max similarity {max_sim:.0%}). Good portfolio diversification."

    return {
        "agent": "Correlation Guard Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "max_correlation": round(max_sim, 4),
            "correlations": top_match[:5],
            "high_correlation_count": len(high_corr),
            "is_duplicate": False,
        },
        "review_state": review_state,
    }
