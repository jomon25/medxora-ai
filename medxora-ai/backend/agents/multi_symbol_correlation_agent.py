"""
Multi-Symbol Correlation Agent — tracks live correlations between EURUSD,
GBPUSD, USDJPY etc. and prevents over-exposure to one market direction.

Uses deterministic Pearson correlation coefficients derived from known
forex pair relationships (proxy for real-time data).
"""

import math


# Known approximate correlations between major forex pairs
PAIR_CORRELATIONS = {
    ("EURUSD", "GBPUSD"): 0.82,
    ("EURUSD", "AUDUSD"): 0.76,
    ("EURUSD", "NZDUSD"): 0.72,
    ("EURUSD", "USDJPY"): -0.68,
    ("EURUSD", "USDCHF"): -0.91,
    ("EURUSD", "USDCAD"): -0.65,
    ("GBPUSD", "AUDUSD"): 0.69,
    ("GBPUSD", "USDJPY"): -0.55,
    ("GBPUSD", "USDCHF"): -0.78,
    ("AUDUSD", "NZDUSD"): 0.88,
    ("AUDUSD", "USDJPY"): -0.45,
    ("USDJPY", "USDCHF"): 0.72,
    ("USDJPY", "USDCAD"): 0.58,
}

CORRELATION_THRESHOLDS = {
    "extreme":  0.85,
    "high":     0.70,
    "moderate": 0.50,
}


def _get_correlation(pair1: str, pair2: str) -> float:
    key = (pair1, pair2)
    rev_key = (pair2, pair1)
    return PAIR_CORRELATIONS.get(key, PAIR_CORRELATIONS.get(rev_key, 0.0))


def _get_direction_exposure(symbols: list[str]) -> dict:
    """Estimate net USD exposure direction across a portfolio of symbols."""
    usd_long = 0
    usd_short = 0
    for s in symbols:
        if s.startswith("USD"):
            usd_long += 1
        elif s.endswith("USD"):
            usd_short += 1
    return {"usd_long": usd_long, "usd_short": usd_short, "net": usd_short - usd_long}


def run_multi_symbol_correlation_agent(
    strategy: dict,
    portfolio_symbols: list[str] | None = None,
    metrics: dict | None = None,
) -> dict:
    symbol = strategy.get("symbol", "EURUSD")
    portfolio_symbols = portfolio_symbols or ["EURUSD", "GBPUSD"]

    # Compute correlation with each portfolio symbol
    correlations = {}
    for ps in portfolio_symbols:
        if ps != symbol:
            corr = _get_correlation(symbol, ps)
            correlations[ps] = round(corr, 3)

    max_corr = max(abs(v) for v in correlations.values()) if correlations else 0.0
    highly_correlated = {k: v for k, v in correlations.items() if abs(v) >= CORRELATION_THRESHOLDS["high"]}
    extreme_corr = {k: v for k, v in correlations.items() if abs(v) >= CORRELATION_THRESHOLDS["extreme"]}

    direction = _get_direction_exposure(portfolio_symbols + [symbol])
    over_exposed = abs(direction["net"]) >= 3

    evidence = [
        f"Strategy symbol: {symbol} | Portfolio: {', '.join(portfolio_symbols)}",
        f"Max correlation: {max_corr:.2f}",
        f"Highly correlated pairs (≥0.70): {', '.join(f'{k}={v:+.2f}' for k, v in highly_correlated.items()) or 'None'}",
        f"USD net direction exposure: {direction['net']:+d} (long={direction['usd_long']}, short={direction['usd_short']})",
    ]
    if over_exposed:
        evidence.append(f"WARNING: Net USD exposure is {direction['net']:+d} — portfolio is directionally concentrated")

    if extreme_corr or over_exposed:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = round(0.70 + max_corr * 0.20, 3)
        reason = (
            f"High correlation risk detected. {symbol} has extreme correlation with "
            f"{', '.join(extreme_corr.keys()) or 'portfolio pairs'}. "
            + ("Portfolio is over-exposed in one USD direction." if over_exposed else "")
        )
    elif highly_correlated:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = round(0.60 + max_corr * 0.15, 3)
        reason = (
            f"{symbol} shows high correlation with {', '.join(highly_correlated.keys())} "
            f"(max corr {max_corr:.2f}). Reduce position size or diversify."
        )
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(0.75 + (1 - max_corr) * 0.15, 3)
        reason = (
            f"{symbol} correlation profile is acceptable (max {max_corr:.2f}). "
            "Portfolio diversification is maintained."
        )

    return {
        "agent": "Multi-Symbol Correlation Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "symbol": symbol,
            "portfolio_symbols": portfolio_symbols,
            "correlations": correlations,
            "max_correlation": round(max_corr, 3),
            "highly_correlated_count": len(highly_correlated),
            "extreme_correlation_count": len(extreme_corr),
            "usd_direction_exposure": direction,
            "over_exposed": over_exposed,
        },
        "review_state": review_state,
    }
