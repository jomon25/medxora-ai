"""
Adaptive Risk Agent — Kelly Criterion based position sizing.

Uses half-Kelly (50% of full Kelly) as a conservative safety margin.
Caps recommendation at MedXora's hard 2.0% risk limit.
"""


def _kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.01
    b = avg_win / avg_loss
    p, q = win_rate, 1 - win_rate
    kelly = (b * p - q) / b
    return max(0.0, kelly)


def run_adaptive_risk_agent(strategy: dict, metrics: dict | None = None) -> dict:
    p = strategy.get("parameters", {})
    sl           = float(p.get("stop_loss", 300) or 300)
    tp           = float(p.get("take_profit", 600) or 600)
    current_risk = float(p.get("risk_percent", 1.0) or 1.0)

    if metrics:
        win_rate  = float(metrics.get("win_rate", 55) or 55) / 100
        pf        = float(metrics.get("profit_factor", 1.2) or 1.2)
        max_dd    = float(metrics.get("max_drawdown", 15) or 15)
        n_trades  = int(metrics.get("total_trades", 50) or 50)
    else:
        win_rate  = min(0.40 + (tp / (tp + sl)) * 0.30, 0.70)
        pf        = (tp / sl) * (win_rate / (1 - win_rate)) if win_rate < 1 else 1.5
        max_dd    = 12.0
        n_trades  = 50

    # Normalised win/loss as % of account
    avg_win_pct  = (tp / 100.0) * current_risk
    avg_loss_pct = (sl / 100.0) * current_risk

    full_kelly  = _kelly(win_rate, avg_win_pct, avg_loss_pct)
    half_kelly  = full_kelly * 0.50

    # Cap at 2% hard limit; drawdown-based further reduction
    recommended = min(half_kelly * 100.0, 2.0)
    if max_dd > 20:
        recommended = min(recommended, 0.50)
    elif max_dd > 15:
        recommended = min(recommended, 1.00)
    recommended = max(recommended, 0.10)

    sample_confidence = min(n_trades / 100.0, 1.0)
    delta = abs(recommended - current_risk)

    evidence = [
        f"Current risk per trade: {current_risk:.2f}%",
        f"Kelly recommended (half-Kelly): {recommended:.2f}%",
        f"Full Kelly fraction: {full_kelly*100:.2f}%",
        f"Win rate: {win_rate*100:.1f}% | R:R ratio: {tp/sl:.2f}",
        f"Profit factor: {pf:.2f} | Max drawdown: {max_dd:.1f}%",
        f"Sample confidence: {sample_confidence*100:.0f}% ({n_trades} trades observed)",
    ]

    if delta < 0.20:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.80
        reason = f"Current risk {current_risk:.1f}% is near optimal Kelly sizing ({recommended:.1f}%). No adjustment needed."
    elif recommended < current_risk:
        decision, risk_level, review_state = "needs_evolution", ("medium" if recommended >= 0.5 else "high"), "Needs Evolution"
        confidence = 0.75
        reason = f"Over-risking detected. Kelly recommends {recommended:.1f}% vs current {current_risk:.1f}%. Reduce risk_percent."
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.68
        reason = f"Under-risking detected. Kelly permits up to {recommended:.1f}%. Increasing risk_percent could improve returns."

    blended_confidence = round(confidence * sample_confidence + confidence * (1 - sample_confidence) * 0.70, 3)

    return {
        "agent": "Adaptive Risk Agent",
        "decision": decision,
        "confidence": blended_confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "current_risk_percent":     current_risk,
            "recommended_risk_percent": round(recommended, 3),
            "full_kelly_pct":           round(full_kelly * 100, 3),
            "half_kelly_pct":           round(half_kelly * 100, 3),
            "win_rate":                 round(win_rate, 4),
            "reward_risk_ratio":        round(tp / sl, 3),
            "sample_confidence":        round(sample_confidence, 3),
            "max_drawdown_observed":    max_dd,
        },
        "review_state": review_state,
    }
