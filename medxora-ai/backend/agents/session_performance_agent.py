SESSIONS = {
    "London":        {"hours": "07:00-16:00 UTC", "volatility": "high",      "trend": "high"},
    "New_York":      {"hours": "12:00-21:00 UTC", "volatility": "high",      "trend": "high"},
    "LN_NY_Overlap": {"hours": "12:00-16:00 UTC", "volatility": "very_high", "trend": "very_high"},
    "Asian":         {"hours": "00:00-09:00 UTC", "volatility": "low",       "trend": "low"},
    "Pacific":       {"hours": "22:00-07:00 UTC", "volatility": "very_low",  "trend": "very_low"},
}

STRATEGY_SESSION_FIT = {
    "ema_rsi":                  ["London", "New_York", "LN_NY_Overlap"],
    "breakout":                 ["LN_NY_Overlap", "London", "New_York"],
    "bollinger_mean_reversion": ["Asian", "Pacific"],
    "macd_crossover":           ["London", "New_York"],
    "supertrend":               ["London", "New_York", "LN_NY_Overlap"],
    "adx_trend_filter":         ["LN_NY_Overlap", "London"],
    "donchian_breakout":        ["London", "LN_NY_Overlap"],
    "multi_tf_ema_rsi":         ["London", "New_York"],
    "news_avoidance":           ["London", "New_York"],
}

TF_SENSITIVITY = {
    "M1": 1.00, "M5": 0.95, "M15": 0.85, "M30": 0.75,
    "H1": 0.60, "H4": 0.35, "D1": 0.12, "W1": 0.05,
}

_VOL_MULT  = {"very_high": 1.30, "high": 1.10, "low": 0.80, "very_low": 0.55}
_TREND_MULT = {"very_high": 1.25, "high": 1.10, "low": 0.80, "very_low": 0.55}


def run_session_performance_agent(strategy: dict, metrics: dict | None = None) -> dict:
    stype = strategy.get("strategy_type", "ema_rsi")
    tf    = strategy.get("timeframe", "M15")
    p     = strategy.get("parameters", {})

    best_sessions = STRATEGY_SESSION_FIT.get(stype, ["London", "New_York"])
    tf_weight     = TF_SENSITIVITY.get(tf, 0.50)
    has_news_filter  = bool(p.get("news_pause_minutes", 0))
    avoids_friday    = bool(p.get("avoid_friday_close", False))

    session_scores: dict[str, float] = {}
    for sess, info in SESSIONS.items():
        base = 1.0 if sess in best_sessions else 0.30
        vol_m   = _VOL_MULT.get(info["volatility"], 1.0)
        trend_m = _TREND_MULT.get(info["trend"], 1.0)

        if stype == "bollinger_mean_reversion" and info["volatility"] in ("very_high", "high"):
            raw = base * 0.45
        elif stype in ("breakout", "donchian_breakout") and info["volatility"] == "very_high":
            raw = base * vol_m
        else:
            raw = base * ((vol_m + trend_m) / 2)

        score = min(raw * tf_weight + (1 - tf_weight) * 0.70, 1.0)
        session_scores[sess] = round(score, 3)

    top_sessions  = sorted(session_scores, key=session_scores.get, reverse=True)[:3]
    worst_session = min(session_scores, key=session_scores.get)
    avg_score     = sum(session_scores.values()) / len(session_scores)

    evidence = [
        f"Strategy '{stype}' fits best in: {', '.join(top_sessions)}",
        f"Timeframe {tf} — session sensitivity: {tf_weight:.2f}",
        f"Avoid '{worst_session}' (score: {session_scores[worst_session]:.2f})",
        f"News filter active: {has_news_filter} | Friday close avoidance: {avoids_friday}",
    ]

    if avg_score >= 0.65:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(min(avg_score + 0.10, 0.92), 3)
        reason = f"Strong session fit. Top sessions: {', '.join(top_sessions[:2])}."
    elif avg_score >= 0.45:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.68
        reason = f"Moderate session fit. Consider restricting to {top_sessions[0]} for cleaner edge."
    else:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.72
        reason = f"Poor session compatibility. Adding a session filter for {top_sessions[0]} is recommended."

    return {
        "agent": "Session Performance Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "session_scores": session_scores,
            "top_sessions": top_sessions,
            "worst_session": worst_session,
            "avg_session_score": round(avg_score, 3),
            "tf_sensitivity_weight": tf_weight,
            "has_news_filter": has_news_filter,
            "avoids_friday_close": avoids_friday,
        },
        "review_state": review_state,
    }
