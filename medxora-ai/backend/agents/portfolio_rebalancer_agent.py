"""
Portfolio Rebalancer Agent — periodically reassigns capital weights across
active strategies based on recent Sharpe ratios and performance metrics.

Uses Equal Risk Contribution (ERC) as base, then overlays Sharpe-based tilt.
"""

import math


MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.40


def _sharpe_weight(sharpe: float) -> float:
    """Map Sharpe ratio to a positive weight (sigmoid-like)."""
    if sharpe <= 0:
        return 0.05
    return min(1.0, max(0.1, math.log1p(sharpe) / 2.0))


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    normalized = {k: v / total for k, v in weights.items()}
    capped = {k: min(v, MAX_WEIGHT) for k, v in normalized.items()}
    total_capped = sum(capped.values())
    return {k: v / total_capped for k, v in capped.items()}


def run_portfolio_rebalancer_agent(
    strategies: list[dict],
    metrics_map: dict[str, dict] | None = None,
) -> dict:
    """
    Parameters
    ----------
    strategies   : list of strategy dicts (must have 'name' key)
    metrics_map  : dict mapping strategy_name → backtest metrics dict
    """
    if not strategies:
        return {
            "agent": "Portfolio Rebalancer Agent",
            "decision": "needs_retest",
            "confidence": 0.50,
            "risk_level": "medium",
            "reason": "No strategies provided for rebalancing.",
            "evidence": ["Empty portfolio — add strategies first."],
            "data": {"weights": {}, "total_strategies": 0},
            "review_state": "Needs Retest",
        }

    metrics_map = metrics_map or {}
    raw_weights: dict[str, float] = {}
    strategy_scores: list[dict] = []

    for s in strategies:
        name = s.get("name", "unknown")
        m = metrics_map.get(name, {})
        sharpe = float(m.get("sharpe_ratio", 0.5) or 0.5)
        pf = float(m.get("profit_factor", 1.0) or 1.0)
        dd = float(m.get("max_drawdown", 20) or 20)
        wr = float(m.get("win_rate", 50) or 50) / 100
        profit = float(m.get("net_profit", 0) or 0)

        sw = _sharpe_weight(sharpe)
        pf_boost = max(0, (pf - 1.0) * 0.3)
        dd_penalty = max(0, (dd - 10) * 0.02)
        raw = max(MIN_WEIGHT, sw + pf_boost - dd_penalty)
        if profit < 0:
            raw = MIN_WEIGHT
        raw_weights[name] = raw
        strategy_scores.append({
            "name": name,
            "sharpe": round(sharpe, 3),
            "profit_factor": round(pf, 3),
            "max_drawdown": round(dd, 1),
            "win_rate": round(wr * 100, 1),
            "net_profit": round(profit, 2),
            "raw_weight": round(raw, 4),
        })

    final_weights = _normalize_weights(raw_weights)
    for score in strategy_scores:
        score["final_weight_pct"] = round(final_weights.get(score["name"], 0) * 100, 1)

    strategy_scores.sort(key=lambda x: x["final_weight_pct"], reverse=True)

    max_w = max(final_weights.values()) if final_weights else 0
    concentration_ok = max_w <= MAX_WEIGHT

    evidence = [
        f"Portfolio: {len(strategies)} strategies rebalanced",
        f"Max weight: {max_w*100:.1f}% | Concentration OK: {concentration_ok}",
    ]
    for sc in strategy_scores[:5]:
        evidence.append(
            f"  {sc['name']}: {sc['final_weight_pct']}% weight | Sharpe {sc['sharpe']} | DD {sc['max_drawdown']}%"
        )

    if concentration_ok and len(strategies) >= 2:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.82
        reason = (
            f"Portfolio of {len(strategies)} strategies rebalanced successfully. "
            f"Max concentration {max_w*100:.1f}% is within limits. "
            f"Top strategy: {strategy_scores[0]['name']} at {strategy_scores[0]['final_weight_pct']}%."
        )
    elif len(strategies) == 1:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.60
        reason = "Only one strategy in portfolio — diversification insufficient. Add more strategies."
    else:
        decision, risk_level, review_state = "needs_evolution", "medium", "Needs Evolution"
        confidence = 0.70
        reason = (
            f"Concentration risk: one strategy holds {max_w*100:.1f}% of capital. "
            "Evolve additional strategies to reduce concentration."
        )

    return {
        "agent": "Portfolio Rebalancer Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "total_strategies": len(strategies),
            "weights": {k: round(v * 100, 1) for k, v in final_weights.items()},
            "strategy_scores": strategy_scores,
            "max_weight_pct": round(max_w * 100, 1),
            "concentration_ok": concentration_ok,
        },
        "review_state": review_state,
    }
