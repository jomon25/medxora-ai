"""
Macro Calendar Agent — monitors economic event calendar and assesses
strategy risk around high-impact events (CPI, NFP, Fed, ECB, etc.)

Uses a deterministic simulated calendar.  Replace _get_upcoming_events()
with a real calendar API (e.g. forexfactory, investing.com) in production.
"""

import random
import hashlib
from datetime import datetime, timezone


HIGH_IMPACT_EVENTS = [
    {"name": "US Non-Farm Payrolls", "impact": "high", "symbol_filter": ["EURUSD", "GBPUSD", "USDJPY"]},
    {"name": "US CPI (Inflation)",   "impact": "high", "symbol_filter": ["EURUSD", "GBPUSD", "USDJPY"]},
    {"name": "Fed Interest Rate Decision", "impact": "high", "symbol_filter": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]},
    {"name": "ECB Interest Rate Decision", "impact": "high", "symbol_filter": ["EURUSD"]},
    {"name": "BOE Interest Rate Decision", "impact": "high", "symbol_filter": ["GBPUSD"]},
    {"name": "US GDP (Quarterly)",   "impact": "medium", "symbol_filter": ["EURUSD", "USDJPY"]},
    {"name": "US Retail Sales",      "impact": "medium", "symbol_filter": ["EURUSD", "GBPUSD"]},
    {"name": "UK CPI",               "impact": "medium", "symbol_filter": ["GBPUSD"]},
    {"name": "Eurozone CPI",         "impact": "medium", "symbol_filter": ["EURUSD"]},
    {"name": "US ISM Manufacturing", "impact": "medium", "symbol_filter": ["EURUSD", "USDJPY"]},
    {"name": "US Initial Jobless Claims", "impact": "low", "symbol_filter": ["EURUSD"]},
    {"name": "Eurozone PMI",         "impact": "low", "symbol_filter": ["EURUSD"]},
]

PAUSE_WINDOWS = {"high": 60, "medium": 30, "low": 0}


def _get_upcoming_events(symbol: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    events = []
    for ev in HIGH_IMPACT_EVENTS:
        if symbol in ev["symbol_filter"] or not ev["symbol_filter"]:
            hours_until = rng.randint(1, 72)
            events.append({
                "name":        ev["name"],
                "impact":      ev["impact"],
                "hours_until": hours_until,
                "direction":   rng.choice(["bullish_expected", "bearish_expected", "neutral"]),
            })
    events.sort(key=lambda e: e["hours_until"])
    return events[:6]


def run_macro_calendar_agent(strategy: dict, metrics: dict | None = None) -> dict:
    symbol = strategy.get("symbol", "EURUSD")
    timeframe = strategy.get("timeframe", "M15")
    name = strategy.get("name", "unknown")

    seed = int(hashlib.md5(f"{name}{symbol}macro".encode()).hexdigest(), 16) & 0xFFFFFF
    events = _get_upcoming_events(symbol, seed)

    # Find soonest high-impact event
    high_events = [e for e in events if e["impact"] == "high"]
    medium_events = [e for e in events if e["impact"] == "medium"]
    soonest_high = high_events[0] if high_events else None
    soonest_medium = medium_events[0] if medium_events else None

    # Short timeframes are more exposed to event volatility
    high_tf_exposure = timeframe in ("M1", "M5", "M15", "M30")

    evidence = [f"Symbol: {symbol} | Timeframe: {timeframe}"]
    for ev in events[:4]:
        evidence.append(f"{ev['impact'].upper()} — {ev['name']}: in {ev['hours_until']}h ({ev['direction'].replace('_', ' ')})")

    if soonest_high and soonest_high["hours_until"] <= 2:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = 0.88
        pause_min = PAUSE_WINDOWS["high"]
        reason = (
            f"HIGH IMPACT event imminent: '{soonest_high['name']}' in {soonest_high['hours_until']}h. "
            f"Recommend pausing strategy for ±{pause_min} minutes around release."
        )
    elif soonest_high and soonest_high["hours_until"] <= 12 and high_tf_exposure:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.72
        reason = (
            f"High-impact event '{soonest_high['name']}' in {soonest_high['hours_until']}h. "
            f"Short timeframe {timeframe} is exposed. Monitor volatility."
        )
    elif soonest_medium and soonest_medium["hours_until"] <= 4 and high_tf_exposure:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.65
        reason = (
            f"Medium-impact event '{soonest_medium['name']}' within 4h on short TF {timeframe}. "
            "Consider tightening stops."
        )
    else:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = 0.78
        next_event = events[0]["name"] if events else "none scheduled"
        next_hours = events[0]["hours_until"] if events else 999
        reason = (
            f"No imminent high-impact events for {symbol}. "
            f"Next scheduled: '{next_event}' in {next_hours}h. Safe window to trade."
        )

    return {
        "agent": "Macro Calendar Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "symbol": symbol,
            "timeframe": timeframe,
            "upcoming_events": events,
            "soonest_high_impact_hours": soonest_high["hours_until"] if soonest_high else None,
            "soonest_high_impact_name": soonest_high["name"] if soonest_high else None,
            "high_tf_exposure": high_tf_exposure,
            "total_events_checked": len(events),
        },
        "review_state": review_state,
    }
