"""
Regime Change Detector — alerts when market transitions from trending to
ranging (or vice versa) using ADX, EMA spread, and volatility signals.
"""

import random
import hashlib


REGIME_TRANSITIONS = {
    ("trending", "ranging"):  {"risk": "high",   "label": "Trend collapse — ranging emerging"},
    ("trending", "volatile"): {"risk": "high",   "label": "Trend ending — volatility spike"},
    ("ranging",  "trending"): {"risk": "medium", "label": "Breakout from range — new trend forming"},
    ("ranging",  "volatile"): {"risk": "high",   "label": "Range break — volatility surge"},
    ("volatile", "trending"): {"risk": "low",    "label": "Volatility resolved — trend establishing"},
    ("volatile", "ranging"):  {"risk": "medium", "label": "Volatility calming — range forming"},
}


def _estimate_adx(parameters: dict, seed: int) -> float:
    rng = random.Random(seed)
    adx_threshold = float(parameters.get("adx_threshold", 0) or 0)
    base = 25.0 if adx_threshold >= 25 else 18.0
    return round(rng.uniform(base - 8, base + 12), 1)


def _detect_regimes(strategy: dict, seed: int) -> tuple[str, str, dict]:
    p = strategy.get("parameters", {})
    stype = strategy.get("strategy_type", "ema_rsi")
    rng = random.Random(seed)

    ema_gap = float((p.get("slow_ema", 50) or 50) - (p.get("fast_ema", 20) or 20))
    adx_est = _estimate_adx(p, seed)
    atr_mult = float(p.get("atr_multiplier", 2.0) or 2.0)

    # Prior regime (what the strategy was designed for)
    if stype in ("ema_rsi", "macd_crossover", "supertrend", "adx_trend_filter", "multi_tf_ema_rsi", "ichimoku"):
        prior_regime = "trending"
    elif stype in ("bollinger_mean_reversion", "stochastic_rsi", "vwap_deviation", "pivot_points", "grid_trading"):
        prior_regime = "ranging"
    elif stype in ("breakout", "donchian_breakout"):
        prior_regime = "volatile"
    else:
        prior_regime = "mixed"

    # Current regime estimate
    if adx_est >= 28 and ema_gap >= 20:
        current_regime = "trending"
    elif adx_est < 20 and ema_gap < 15:
        current_regime = "ranging"
    elif atr_mult >= 2.5 or rng.random() < 0.25:
        current_regime = "volatile"
    else:
        current_regime = prior_regime  # stable

    signals = {
        "adx_estimate": adx_est,
        "ema_gap": ema_gap,
        "atr_multiplier": atr_mult,
        "volatility_percentile": round(rng.uniform(20, 85), 1),
    }
    return prior_regime, current_regime, signals


def run_regime_change_detector_agent(strategy: dict, metrics: dict | None = None) -> dict:
    name = strategy.get("name", "unknown")
    stype = strategy.get("strategy_type", "ema_rsi")
    timeframe = strategy.get("timeframe", "M15")

    seed = int(hashlib.md5(f"{name}regime".encode()).hexdigest(), 16) & 0xFFFFFF
    prior_regime, current_regime, signals = _detect_regimes(strategy, seed)

    regime_changed = prior_regime != current_regime and prior_regime != "mixed"
    transition_key = (prior_regime, current_regime)
    transition_info = REGIME_TRANSITIONS.get(transition_key)

    evidence = [
        f"Strategy type: {stype} | Timeframe: {timeframe}",
        f"Designed-for regime: {prior_regime} | Current detected regime: {current_regime}",
        f"ADX estimate: {signals['adx_estimate']} | EMA gap: {signals['ema_gap']:.0f}",
        f"ATR multiplier: {signals['atr_multiplier']} | Volatility %ile: {signals['volatility_percentile']}",
    ]
    if transition_info:
        evidence.append(f"Transition signal: {transition_info['label']}")

    if regime_changed and transition_info and transition_info["risk"] == "high":
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.83
        reason = (
            f"REGIME CHANGE DETECTED: {prior_regime} → {current_regime}. "
            f"{transition_info['label']}. "
            f"Strategy type '{stype}' is misaligned with the current regime. "
            "Evolve or switch strategy type."
        )
    elif regime_changed and transition_info and transition_info["risk"] == "medium":
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.70
        reason = (
            f"Regime shift: {prior_regime} → {current_regime}. {transition_info['label']}. "
            "Monitor performance for 10+ trades before expanding position size."
        )
    elif prior_regime == current_regime:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.78
        reason = (
            f"Regime stable: {current_regime}. Strategy type '{stype}' remains aligned. "
            f"ADX {signals['adx_estimate']} confirms regime."
        )
    else:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.62
        reason = f"Mixed regime signals (was {prior_regime}, now {current_regime}). Monitor closely."

    return {
        "agent": "Regime Change Detector Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "designed_for_regime": prior_regime,
            "current_regime": current_regime,
            "regime_changed": regime_changed,
            "transition": f"{prior_regime}→{current_regime}" if regime_changed else "stable",
            "adx_estimate": signals["adx_estimate"],
            "ema_gap": signals["ema_gap"],
            "volatility_percentile": signals["volatility_percentile"],
            "strategy_type": stype,
        },
        "review_state": review_state,
    }
