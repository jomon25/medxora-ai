"""
Alert & Notification Agent — generates structured alerts when a strategy
hits milestones: profit targets, drawdown limits, win-rate thresholds.

Alerts are returned as structured objects; wire them to email/Telegram/
Discord in production via the notification dispatcher.
"""

from datetime import datetime, timezone


ALERT_RULES = [
    {
        "id":        "profit_target_hit",
        "label":     "Profit Target Reached",
        "severity":  "success",
        "check":     lambda m, cfg: float(m.get("net_profit", 0)) >= cfg.get("profit_target", 1000),
        "message":   lambda m, cfg: f"🎯 Profit target ${cfg.get('profit_target', 1000):.0f} reached! Net profit: ${float(m.get('net_profit', 0)):.0f}",
    },
    {
        "id":        "drawdown_limit_hit",
        "label":     "Drawdown Limit Breached",
        "severity":  "critical",
        "check":     lambda m, cfg: float(m.get("max_drawdown", 0)) >= cfg.get("max_drawdown_limit", 20),
        "message":   lambda m, cfg: f"🚨 Drawdown limit {cfg.get('max_drawdown_limit', 20):.0f}% breached! Current: {float(m.get('max_drawdown', 0)):.1f}%",
    },
    {
        "id":        "win_rate_low",
        "label":     "Win Rate Warning",
        "severity":  "warning",
        "check":     lambda m, cfg: float(m.get("win_rate", 100)) < cfg.get("min_win_rate", 45),
        "message":   lambda m, cfg: f"⚠️ Win rate dropped to {float(m.get('win_rate', 0)):.1f}% (min: {cfg.get('min_win_rate', 45):.0f}%)",
    },
    {
        "id":        "profit_factor_low",
        "label":     "Profit Factor Warning",
        "severity":  "warning",
        "check":     lambda m, cfg: float(m.get("profit_factor", 99)) < cfg.get("min_profit_factor", 1.2),
        "message":   lambda m, cfg: f"⚠️ Profit factor {float(m.get('profit_factor', 0)):.2f} below minimum {cfg.get('min_profit_factor', 1.2):.1f}",
    },
    {
        "id":        "new_best_profit",
        "label":     "New Profit High",
        "severity":  "info",
        "check":     lambda m, cfg: float(m.get("net_profit", 0)) > cfg.get("previous_best", 0),
        "message":   lambda m, cfg: f"📈 New profit record! ${float(m.get('net_profit', 0)):.0f} (previous best: ${cfg.get('previous_best', 0):.0f})",
    },
    {
        "id":        "trade_count_milestone",
        "label":     "Trade Milestone",
        "severity":  "info",
        "check":     lambda m, cfg: int(m.get("total_trades", 0)) >= cfg.get("trade_milestone", 100),
        "message":   lambda m, cfg: f"🏆 {int(m.get('total_trades', 0))} trades completed — milestone reached!",
    },
]


def run_alert_notification_agent(
    strategy: dict,
    metrics: dict | None = None,
    config: dict | None = None,
) -> dict:
    """
    Parameters
    ----------
    config : optional dict with alert thresholds:
        - profit_target        (default 1000)
        - max_drawdown_limit   (default 20)
        - min_win_rate         (default 45)
        - min_profit_factor    (default 1.2)
        - previous_best        (default 0)
        - trade_milestone      (default 100)
    """
    name = strategy.get("name", "unknown")
    cfg = config or {}
    m = metrics or {}

    fired_alerts: list[dict] = []
    for rule in ALERT_RULES:
        try:
            if rule["check"](m, cfg):
                fired_alerts.append({
                    "id":       rule["id"],
                    "label":    rule["label"],
                    "severity": rule["severity"],
                    "message":  rule["message"](m, cfg),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "strategy": name,
                })
        except Exception:
            pass

    critical_alerts = [a for a in fired_alerts if a["severity"] == "critical"]
    warning_alerts  = [a for a in fired_alerts if a["severity"] == "warning"]
    success_alerts  = [a for a in fired_alerts if a["severity"] == "success"]
    info_alerts     = [a for a in fired_alerts if a["severity"] == "info"]

    evidence = [f"Strategy: {name}", f"Alerts fired: {len(fired_alerts)}"]
    for alert in fired_alerts:
        evidence.append(f"  [{alert['severity'].upper()}] {alert['message']}")
    if not fired_alerts:
        evidence.append("No alert thresholds breached — all systems nominal.")

    if critical_alerts:
        decision, risk_level, review_state = "reject", "high", "Rejected"
        confidence = 0.95
        reason = f"CRITICAL ALERT: {critical_alerts[0]['message']} Immediate intervention required."
    elif warning_alerts:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.78
        reason = f"Warning alerts: {'; '.join(a['message'] for a in warning_alerts[:2])}. Review parameters."
    elif success_alerts or info_alerts:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.80
        reason = f"Positive alerts: {'; '.join(a['message'] for a in (success_alerts + info_alerts)[:2])}."
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.75
        reason = f"Strategy '{name}' is operating within all defined alert thresholds. No action needed."

    return {
        "agent": "Alert & Notification Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "strategy_name": name,
            "alerts": fired_alerts,
            "n_critical": len(critical_alerts),
            "n_warning": len(warning_alerts),
            "n_success": len(success_alerts),
            "n_info": len(info_alerts),
            "total_alerts": len(fired_alerts),
            "thresholds_used": cfg,
        },
        "review_state": review_state,
    }
