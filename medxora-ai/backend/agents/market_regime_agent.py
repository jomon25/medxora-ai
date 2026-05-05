from collections import Counter


REGIME_STRATEGY_MAP = {
    "trending": ["ema_rsi", "macd_crossover", "supertrend", "adx_trend_filter", "multi_tf_ema_rsi"],
    "ranging":  ["bollinger_mean_reversion", "donchian_breakout"],
    "volatile": ["breakout", "donchian_breakout", "supertrend"],
    "mixed":    ["news_avoidance", "multi_tf_ema_rsi", "ema_rsi"],
}


def _classify_regime(strategy: dict, metrics: dict | None = None) -> tuple[str, float]:
    p = strategy.get("parameters", {})
    stype = strategy.get("strategy_type", "ema_rsi")

    adx_threshold = float(p.get("adx_threshold", 0) or 0)
    atr_mult = float(p.get("atr_multiplier", 0) or 0)
    ema_gap = float((p.get("slow_ema", 50) or 50) - (p.get("fast_ema", 20) or 20))

    signals = []

    if adx_threshold >= 25:
        signals.append("trending")
    if stype == "bollinger_mean_reversion":
        signals.append("ranging")
    if stype in ("breakout", "donchian_breakout") and atr_mult >= 2.0:
        signals.append("volatile")
    if ema_gap >= 30:
        signals.append("trending")
    elif ema_gap < 15:
        signals.append("ranging")
    if stype in ("macd_crossover", "supertrend", "adx_trend_filter"):
        signals.append("trending")
    if stype == "news_avoidance":
        signals.append("mixed")

    if metrics:
        wr = float(metrics.get("win_rate", 50) or 50)
        pf = float(metrics.get("profit_factor", 1.0) or 1.0)
        dd = float(metrics.get("max_drawdown", 10) or 10)
        if wr > 60 and pf > 1.5:
            signals.append("trending")
        if wr < 45 and pf > 1.5:
            signals.append("ranging")
        if dd > 15:
            signals.append("volatile")

    if not signals:
        signals.append("mixed")

    counts = Counter(signals)
    top_regime, top_count = counts.most_common(1)[0]
    confidence = min(0.50 + top_count * 0.15, 0.92)
    return top_regime, round(confidence, 3)


def run_market_regime_agent(strategy: dict, metrics: dict | None = None) -> dict:
    regime, confidence = _classify_regime(strategy, metrics)
    stype = strategy.get("strategy_type", "ema_rsi")
    compatible = REGIME_STRATEGY_MAP.get(regime, [])
    fit = stype in compatible

    p = strategy.get("parameters", {})
    ema_gap = float((p.get("slow_ema", 50) or 50) - (p.get("fast_ema", 20) or 20))
    adx_thresh = p.get("adx_threshold", 0)

    evidence = [
        f"Detected market regime: {regime}",
        f"Strategy type '{stype}' {'fits' if fit else 'does not fit'} the {regime} regime",
        f"EMA gap: {ema_gap:.0f} — {'wide/trending' if ema_gap >= 20 else 'narrow/ranging'}",
        f"Recommended types for {regime}: {', '.join(compatible)}",
    ]
    if adx_thresh:
        evidence.append(f"ADX threshold {adx_thresh} — {'strong trend filter' if adx_thresh >= 25 else 'weak filter'}")

    if fit:
        return {
            "agent": "Market Regime Agent",
            "decision": "approve",
            "confidence": confidence,
            "risk_level": "low",
            "reason": f"Strategy type '{stype}' is well-suited for the detected {regime} regime.",
            "evidence": evidence,
            "data": {"regime": regime, "regime_fit": True, "compatible_types": compatible, "ema_gap": ema_gap},
            "review_state": "Approved",
        }

    return {
        "agent": "Market Regime Agent",
        "decision": "needs_evolution",
        "confidence": confidence,
        "risk_level": "medium",
        "reason": (
            f"Strategy type '{stype}' is not optimal for the {regime} regime. "
            f"Consider evolving toward: {compatible[0] if compatible else 'mixed'}."
        ),
        "evidence": evidence,
        "data": {"regime": regime, "regime_fit": False, "compatible_types": compatible, "ema_gap": ema_gap},
        "review_state": "Needs Evolution",
    }
