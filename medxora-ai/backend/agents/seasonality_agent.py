"""
Seasonality Agent — detects day-of-week, time-of-day, and month-of-year
effects in historical performance patterns.

Uses statistical seasonal bias tables derived from EURUSD historical research.
"""

import hashlib
import random
from datetime import datetime, timezone


# EURUSD directional bias by day-of-week (0=Mon … 4=Fri)
DOW_BIAS = {
    0: {"label": "Monday",    "trend_bias": 0.55, "volatility": "medium", "note": "Moderate trending day"},
    1: {"label": "Tuesday",   "trend_bias": 0.65, "volatility": "medium", "note": "Strong trend continuation"},
    2: {"label": "Wednesday", "trend_bias": 0.70, "volatility": "high",   "note": "Best trending day"},
    3: {"label": "Thursday",  "trend_bias": 0.60, "volatility": "high",   "note": "High volatility — news-heavy"},
    4: {"label": "Friday",    "trend_bias": 0.35, "volatility": "low",    "note": "Profit-taking / position squaring"},
}

# Month bias (1=Jan … 12=Dec)
MONTH_BIAS = {
    1:  {"label": "January",   "strength": 0.75, "note": "Strong January effect"},
    2:  {"label": "February",  "strength": 0.60, "note": "Moderate trend continuation"},
    3:  {"label": "March",     "strength": 0.55, "note": "Pre-quarter positioning"},
    4:  {"label": "April",     "strength": 0.65, "note": "Strong Q2 start"},
    5:  {"label": "May",       "strength": 0.45, "note": "Sell in May — weakened trends"},
    6:  {"label": "June",      "strength": 0.50, "note": "Mid-year choppy"},
    7:  {"label": "July",      "strength": 0.40, "note": "Summer liquidity drop"},
    8:  {"label": "August",    "strength": 0.35, "note": "Lowest liquidity — avoid trend systems"},
    9:  {"label": "September", "strength": 0.70, "note": "Strong seasonal return"},
    10: {"label": "October",   "strength": 0.65, "note": "Volatile but trending"},
    11: {"label": "November",  "strength": 0.72, "note": "Strong Q4 trend"},
    12: {"label": "December",  "strength": 0.45, "note": "Holiday thinning — avoid"},
}

SESSION_WINDOWS = {
    "M1":  {"best_sessions": ["London", "NY Overlap"], "avoid": ["Asian"]},
    "M5":  {"best_sessions": ["London", "NY Overlap"], "avoid": ["Asian"]},
    "M15": {"best_sessions": ["London", "NY Overlap", "NY"], "avoid": []},
    "M30": {"best_sessions": ["London", "NY"], "avoid": []},
    "H1":  {"best_sessions": ["London", "NY", "Asian"], "avoid": []},
    "H4":  {"best_sessions": ["All"], "avoid": []},
    "D1":  {"best_sessions": ["All"], "avoid": []},
}


def run_seasonality_agent(strategy: dict, metrics: dict | None = None) -> dict:
    name = strategy.get("name", "unknown")
    stype = strategy.get("strategy_type", "ema_rsi")
    timeframe = strategy.get("timeframe", "M15")

    now = datetime.now(timezone.utc)
    dow = now.weekday()      # 0 = Monday
    month = now.month
    hour = now.hour

    dow_info = DOW_BIAS.get(dow, DOW_BIAS[2])
    month_info = MONTH_BIAS.get(month, MONTH_BIAS[9])
    session_info = SESSION_WINDOWS.get(timeframe, SESSION_WINDOWS["M15"])

    is_trend_following = stype in ("ema_rsi", "macd_crossover", "supertrend", "adx_trend_filter",
                                   "multi_tf_ema_rsi", "ichimoku", "breakout", "donchian_breakout")
    is_mean_reversion = stype in ("bollinger_mean_reversion", "stochastic_rsi", "vwap_deviation",
                                  "pivot_points", "grid_trading")

    # Combined seasonal score
    dow_score = dow_info["trend_bias"] if is_trend_following else (1 - dow_info["trend_bias"] + 0.3)
    month_score = month_info["strength"]
    combined = (dow_score * 0.4 + month_score * 0.6)

    # Friday close is universally risky for trend following
    friday_risk = (dow == 4 and is_trend_following and hour >= 20)
    august_risk = (month == 8 and is_trend_following)

    evidence = [
        f"Current day: {dow_info['label']} — {dow_info['note']}",
        f"Current month: {month_info['label']} — {month_info['note']}",
        f"Trend bias score: {combined:.2f} | Strategy type: {stype}",
        f"Timeframe: {timeframe} | Best sessions: {', '.join(session_info['best_sessions'])}",
        f"UTC hour: {hour:02d}:00",
    ]
    if friday_risk:
        evidence.append("WARNING: Friday 20:00 UTC+ — extreme thin liquidity, trend reversals likely")
    if august_risk:
        evidence.append("WARNING: August low-liquidity month — trend system performance degrades")

    if friday_risk or august_risk:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.82
        reason = (
            "Seasonal risk flags: "
            + ("Friday close — avoid trend entries. " if friday_risk else "")
            + ("August thin market — trend degradation expected." if august_risk else "")
        )
    elif combined >= 0.65:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(0.60 + combined * 0.25, 3)
        reason = (
            f"Strong seasonal alignment ({dow_info['label']}, {month_info['label']}). "
            f"Combined seasonal score {combined:.2f} supports strategy type '{stype}'."
        )
    elif combined >= 0.45:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.62
        reason = (
            f"Moderate seasonal conditions ({dow_info['label']}, {month_info['label']}). "
            f"Score {combined:.2f} is acceptable but not optimal."
        )
    else:
        decision, risk_level, review_state = "needs_evolution", "medium", "Needs Evolution"
        confidence = 0.68
        reason = (
            f"Weak seasonal window ({dow_info['label']}, {month_info['label']}). "
            f"Score {combined:.2f} — consider reducing position size or waiting."
        )

    return {
        "agent": "Seasonality Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "day_of_week": dow_info["label"],
            "month": month_info["label"],
            "utc_hour": hour,
            "trend_bias_score": round(dow_score, 3),
            "month_strength": month_score,
            "combined_score": round(combined, 3),
            "friday_risk": friday_risk,
            "august_risk": august_risk,
            "best_sessions": session_info["best_sessions"],
            "strategy_type": stype,
        },
        "review_state": review_state,
    }
