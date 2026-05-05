"""
Sentiment Analysis Agent — scores market sentiment per symbol using
simulated news and social media signals (rule-based, no external API needed).

In production: replace _fetch_sentiment() with a real news/social API.
"""

import random
import hashlib


BULLISH_KEYWORDS = [
    "breakout", "rally", "surge", "bullish", "uptrend", "buy",
    "support", "recovery", "momentum", "strong", "beat", "upgrade",
]
BEARISH_KEYWORDS = [
    "selloff", "crash", "bearish", "downtrend", "sell", "resistance",
    "reversal", "weak", "miss", "downgrade", "risk", "uncertainty",
]

SYMBOL_BIAS = {
    "EURUSD": 0.0,
    "GBPUSD": 0.05,
    "USDJPY": -0.05,
    "AUDUSD": 0.03,
    "USDCAD": -0.03,
    "NZDUSD": 0.02,
    "USDCHF": -0.02,
}


def _fetch_sentiment(symbol: str, seed: int) -> dict:
    """Deterministic mock sentiment; replace with real API in production."""
    rng = random.Random(seed)
    base_bias = SYMBOL_BIAS.get(symbol, 0.0)
    raw_score = rng.uniform(-1.0, 1.0) + base_bias
    raw_score = max(-1.0, min(1.0, raw_score))

    n_articles = rng.randint(12, 80)
    bullish_articles = int((raw_score * 0.5 + 0.5) * n_articles)
    bearish_articles = n_articles - bullish_articles
    social_score = rng.uniform(-0.8, 0.8) + base_bias * 0.5

    return {
        "raw_score": round(raw_score, 4),
        "social_score": round(social_score, 4),
        "composite": round((raw_score * 0.6 + social_score * 0.4), 4),
        "n_articles": n_articles,
        "bullish_articles": bullish_articles,
        "bearish_articles": bearish_articles,
    }


def _label(score: float) -> str:
    if score >= 0.4:
        return "strongly_bullish"
    if score >= 0.15:
        return "moderately_bullish"
    if score <= -0.4:
        return "strongly_bearish"
    if score <= -0.15:
        return "moderately_bearish"
    return "neutral"


def run_sentiment_agent(strategy: dict, metrics: dict | None = None) -> dict:
    symbol = strategy.get("symbol", "EURUSD")
    stype = strategy.get("strategy_type", "ema_rsi")

    seed = int(hashlib.md5(f"{strategy['name']}{symbol}".encode()).hexdigest(), 16) & 0xFFFFFF
    sent = _fetch_sentiment(symbol, seed)
    composite = sent["composite"]
    label = _label(composite)

    is_trend_following = stype in ("ema_rsi", "macd_crossover", "supertrend", "adx_trend_filter",
                                   "multi_tf_ema_rsi", "ichimoku", "breakout", "donchian_breakout")
    is_mean_reversion = stype in ("bollinger_mean_reversion", "stochastic_rsi", "vwap_deviation",
                                  "pivot_points", "grid_trading")

    alignment = "neutral"
    if is_trend_following and composite > 0.15:
        alignment = "aligned"
    elif is_trend_following and composite < -0.15:
        alignment = "counter"
    elif is_mean_reversion and abs(composite) > 0.4:
        alignment = "counter"
    elif is_mean_reversion:
        alignment = "aligned"

    if alignment == "aligned" and abs(composite) > 0.15:
        decision, risk_level, review_state = "approve", "low", "Approved"
        confidence = round(0.60 + abs(composite) * 0.25, 3)
        reason = (
            f"Sentiment is {label.replace('_', ' ')} for {symbol} and aligns with the "
            f"strategy's {stype} approach. Composite score: {composite:+.2f}."
        )
    elif label == "neutral":
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.55
        reason = f"Sentiment for {symbol} is neutral (score {composite:+.2f}). Monitor for direction."
    elif alignment == "counter" and abs(composite) > 0.3:
        decision, risk_level, review_state = "needs_evolution", "high", "Needs Evolution"
        confidence = round(0.65 + abs(composite) * 0.2, 3)
        reason = (
            f"Sentiment is {label.replace('_', ' ')} for {symbol} but counter to the "
            f"strategy's direction. Consider delaying or adjusting parameters."
        )
    else:
        decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
        confidence = 0.58
        reason = f"Mixed sentiment signals for {symbol}. Score {composite:+.2f} — proceed with caution."

    evidence = [
        f"Symbol: {symbol} | Strategy type: {stype}",
        f"Composite sentiment score: {composite:+.2f} ({label.replace('_', ' ')})",
        f"News articles: {sent['n_articles']} ({sent['bullish_articles']} bullish, {sent['bearish_articles']} bearish)",
        f"Social media score: {sent['social_score']:+.2f}",
        f"Strategy–sentiment alignment: {alignment}",
    ]

    return {
        "agent": "Sentiment Analysis Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "symbol": symbol,
            "sentiment_label": label,
            "composite_score": composite,
            "news_score": sent["raw_score"],
            "social_score": sent["social_score"],
            "n_articles": sent["n_articles"],
            "bullish_articles": sent["bullish_articles"],
            "bearish_articles": sent["bearish_articles"],
            "strategy_alignment": alignment,
        },
        "review_state": review_state,
    }
