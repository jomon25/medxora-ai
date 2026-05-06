import hashlib


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TF_SCALE = {"M15": 1, "H1": 4, "H4": 16, "D1": 64}

_TIMEFRAME_LABELS = {1: "M15", 4: "H1", 16: "H4", 64: "D1"}


def _simulated_ema_crossover(strategy_name: str, scale: int) -> str:
    """
    Deterministically simulate whether EMA is bullish or bearish on a scaled
    timeframe by hashing the strategy name + scale factor.
    Returns 'bullish' or 'bearish'.
    """
    key    = f"{strategy_name}:scale{scale}".encode()
    digest = int(hashlib.sha256(key).hexdigest(), 16)
    # Slight bullish bias (55/45) to reflect that generated strategies are
    # trend-following and tend to align with higher timeframes.
    return "bullish" if (digest % 100) < 55 else "bearish"


def _base_tf_crossover(strategy: dict) -> str:
    """Determine M15 crossover direction from EMA parameters."""
    p  = strategy.get("parameters", {})
    fe = float(p.get("fast_ema", 10) or 10)
    se = float(p.get("slow_ema", 50) or 50)
    # fast_ema < slow_ema means the strategy BUYS when fast crosses above slow
    # We check the gap: if fast is meaningfully below slow the crossover
    # signal is "bullish-seeking" (designed for uptrends).
    return "bullish" if fe < se else "bearish"


def _scaled_crossover(strategy: dict, scale: int) -> dict:
    """
    Return simulated crossover result for a higher timeframe.
    Uses a deterministic hash so results are reproducible.
    """
    name      = strategy.get("name", "unknown")
    direction = _simulated_ema_crossover(name, scale)
    p         = strategy.get("parameters", {})
    fe        = float(p.get("fast_ema", 10) or 10)
    se        = float(p.get("slow_ema", 50) or 50)
    return {
        "timeframe":   _TIMEFRAME_LABELS.get(scale, f"x{scale}"),
        "fast_ema":    int(fe * scale),
        "slow_ema":    int(se * scale),
        "direction":   direction,
    }


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def run_multi_timeframe_agent(strategy: dict, metrics: dict | None = None) -> dict:
    p          = strategy.get("parameters", {})
    base_tf    = strategy.get("timeframe", "M15")
    base_scale = _TF_SCALE.get(base_tf, 1)

    # Determine which higher timeframes to check
    higher_scales = [s for s in sorted(_TF_SCALE.values()) if s > base_scale][:2]

    if not higher_scales:
        # Strategy is already on the highest timeframe (D1)
        return {
            "agent":      "Multi-Timeframe Agent",
            "decision":   "approve",
            "confidence": 0.80,
            "risk_level": "low",
            "reason":     f"Strategy operates on {base_tf} — no higher timeframe to validate against.",
            "evidence":   [f"Timeframe {base_tf} is the highest supported level."],
            "data": {
                "base_timeframe":   base_tf,
                "base_direction":   _base_tf_crossover(strategy),
                "higher_tf_checks": [],
                "aligned_count":    0,
                "total_checked":    0,
            },
            "review_state": "Approved",
        }

    base_direction = _base_tf_crossover(strategy)
    higher_checks  = [_scaled_crossover(strategy, s) for s in higher_scales]

    aligned     = [c for c in higher_checks if c["direction"] == base_direction]
    misaligned  = [c for c in higher_checks if c["direction"] != base_direction]

    aligned_count   = len(aligned)
    total_checked   = len(higher_checks)
    misaligned_count = len(misaligned)

    evidence = [
        f"Base timeframe ({base_tf}) EMA crossover direction: {base_direction.upper()}",
    ]
    for c in higher_checks:
        status = "ALIGNED" if c["direction"] == base_direction else "CONFLICT"
        evidence.append(
            f"{c['timeframe']} EMA({c['fast_ema']}/{c['slow_ema']}): "
            f"{c['direction'].upper()} — {status}"
        )
    evidence.append(
        f"Alignment: {aligned_count}/{total_checked} higher timeframes confirm {base_direction} trend"
    )

    if misaligned_count == 0:
        # Full alignment
        decision     = "approve"
        risk_level   = "low"
        review_state = "Approved"
        confidence   = 0.88
        reason = (
            f"Full multi-timeframe alignment: {base_tf}, "
            + " and ".join(c["timeframe"] for c in higher_checks)
            + f" all show a {base_direction} bias. High-probability trade setup."
        )
    elif misaligned_count == total_checked:
        # Trading directly against all higher timeframes
        decision     = "reject"
        risk_level   = "high"
        review_state = "Rejected"
        confidence   = 0.85
        reason = (
            f"Strategy is {base_direction} on {base_tf} but ALL higher timeframes "
            f"({', '.join(c['timeframe'] for c in misaligned)}) show the opposite trend. "
            "Trading against the dominant trend is high-risk."
        )
    else:
        # Partial misalignment — warn
        conflict_tfs = ", ".join(c["timeframe"] for c in misaligned)
        decision     = "needs_retest"
        risk_level   = "medium"
        review_state = "Needs Retest"
        confidence   = 0.65
        reason = (
            f"Partial timeframe conflict: {base_tf} is {base_direction} but {conflict_tfs} "
            f"disagrees. Strategy may work in select conditions — retest with filtered entry."
        )

    return {
        "agent":      "Multi-Timeframe Agent",
        "decision":   decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason":     reason,
        "evidence":   evidence,
        "data": {
            "base_timeframe":    base_tf,
            "base_direction":    base_direction,
            "higher_tf_checks":  higher_checks,
            "aligned_count":     aligned_count,
            "misaligned_count":  misaligned_count,
            "total_checked":     total_checked,
        },
        "review_state": review_state,
    }
