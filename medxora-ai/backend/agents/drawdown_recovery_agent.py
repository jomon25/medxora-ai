"""
Drawdown Recovery Agent — detects when a strategy is in extended drawdown
and triggers automated parameter adjustment recommendations.
"""


DRAWDOWN_THRESHOLDS = {
    "critical": 25.0,
    "high":     15.0,
    "moderate":  8.0,
    "low":       3.0,
}

RECOVERY_PLAYBOOK = {
    "critical": {
        "action": "halt_and_rebuild",
        "risk_reduction": 0.50,
        "description": "Reduce risk by 50%, halt new entries, trigger full re-evolution.",
    },
    "high": {
        "action": "reduce_risk",
        "risk_reduction": 0.30,
        "description": "Reduce position size by 30%, tighten stop-loss by 10%.",
    },
    "moderate": {
        "action": "tighten_parameters",
        "risk_reduction": 0.15,
        "description": "Tighten stops by 5%, reduce risk by 15%, skip low-confidence signals.",
    },
    "low": {
        "action": "monitor",
        "risk_reduction": 0.0,
        "description": "Minor drawdown within normal range — continue monitoring.",
    },
}


def _assess_recovery_potential(metrics: dict) -> float:
    """Estimate recovery potential based on historical win rate and profit factor."""
    pf = float(metrics.get("profit_factor", 1.0) or 1.0)
    wr = float(metrics.get("win_rate", 50) or 50) / 100
    sharpe = float(metrics.get("sharpe_ratio", 0.5) or 0.5)
    potential = min(1.0, (pf - 1.0) * 0.4 + wr * 0.4 + sharpe * 0.2)
    return round(max(0.0, potential), 3)


def run_drawdown_recovery_agent(strategy: dict, metrics: dict | None = None) -> dict:
    p = strategy.get("parameters", {})
    current_risk = float(p.get("risk_percent", 1.0) or 1.0)
    sl = float(p.get("stop_loss", 300) or 300)
    tp = float(p.get("take_profit", 600) or 600)

    if metrics:
        current_dd = float(metrics.get("max_drawdown", 0) or 0)
        win_rate = float(metrics.get("win_rate", 50) or 50)
        pf = float(metrics.get("profit_factor", 1.0) or 1.0)
        net_profit = float(metrics.get("net_profit", 0) or 0)
        total_trades = int(metrics.get("total_trades", 0) or 0)
    else:
        current_dd = 0.0
        win_rate = 50.0
        pf = 1.0
        net_profit = 0.0
        total_trades = 0

    # Classify drawdown severity
    if current_dd >= DRAWDOWN_THRESHOLDS["critical"]:
        severity = "critical"
    elif current_dd >= DRAWDOWN_THRESHOLDS["high"]:
        severity = "high"
    elif current_dd >= DRAWDOWN_THRESHOLDS["moderate"]:
        severity = "moderate"
    else:
        severity = "low"

    playbook = RECOVERY_PLAYBOOK[severity]
    recovery_potential = _assess_recovery_potential(metrics or {})

    # Compute recommended adjustments
    new_risk = round(current_risk * (1 - playbook["risk_reduction"]), 3)
    new_risk = max(0.10, new_risk)
    new_sl = round(sl * 0.90, 0) if severity in ("critical", "high") else sl
    recommended_generations = 5 if severity == "critical" else (3 if severity == "high" else 2)

    evidence = [
        f"Current drawdown: {current_dd:.1f}% (severity: {severity})",
        f"Win rate: {win_rate:.1f}% | Profit factor: {pf:.2f} | Net profit: ${net_profit:.0f}",
        f"Current risk per trade: {current_risk:.2f}% → Recommended: {new_risk:.2f}%",
        f"Recovery potential score: {recovery_potential:.2f}/1.00",
        f"Playbook: {playbook['description']}",
        f"Total trades observed: {total_trades}",
    ]

    if severity == "critical":
        decision, risk_level, review_state = "reject", "high", "Rejected"
        confidence = 0.92
        reason = (
            f"Critical drawdown of {current_dd:.1f}% detected. Strategy must be halted. "
            f"Trigger re-evolution with {recommended_generations} generations and reduced risk {new_risk:.2f}%."
        )
    elif severity == "high":
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.85
        reason = (
            f"High drawdown of {current_dd:.1f}% — reduce risk to {new_risk:.2f}%, "
            f"tighten stops, and evolve parameters over {recommended_generations} generations."
        )
    elif severity == "moderate":
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.72
        reason = (
            f"Moderate drawdown of {current_dd:.1f}%. Reduce risk to {new_risk:.2f}% "
            "and tighten parameters. Monitor next 10 trades."
        )
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.80
        reason = (
            f"Drawdown of {current_dd:.1f}% is within normal range. "
            f"Current risk {current_risk:.2f}% is appropriate. No intervention needed."
        )

    return {
        "agent": "Drawdown Recovery Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "current_drawdown_pct": current_dd,
            "severity": severity,
            "recovery_potential": recovery_potential,
            "recommended_risk_percent": new_risk,
            "recommended_stop_loss": new_sl,
            "recommended_evolution_generations": recommended_generations,
            "playbook_action": playbook["action"],
            "risk_reduction_applied": playbook["risk_reduction"],
        },
        "review_state": review_state,
    }
