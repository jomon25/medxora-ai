"""
News Sentiment NLP Agent — simulates FinBERT-style financial news sentiment
analysis for the strategy's currency pair.

In production: replace the simulated headline generation and scoring with a
real FinBERT inference call (e.g. via HuggingFace transformers or a hosted API).
Determinism: seeded on hash(symbol + current weekday number) so results are
stable within the same trading day but shift day-to-day.
"""

import hashlib
import random
from datetime import datetime


# ---------------------------------------------------------------------------
# Headline templates per pair component
# ---------------------------------------------------------------------------

_HEADLINE_TEMPLATES = {
    "EUR": [
        "EUR strengthens on ECB rate decision",
        "Euro zone inflation data beats expectations, EUR rallies",
        "ECB holds rates steady; EUR traders await forward guidance",
        "European manufacturing PMI disappoints, EUR under pressure",
        "EUR/USD climbs as risk appetite returns to markets",
        "ECB minutes signal dovish tilt, EUR weakens broadly",
        "Euro gains as German GDP surprises to the upside",
        "EU-US trade tensions resurface, pressuring EUR",
    ],
    "GBP": [
        "GBP rises as Bank of England signals rate hike path",
        "Sterling gains amid positive UK employment data",
        "Brexit trade frictions resurface, weighing on GBP",
        "UK CPI misses forecast; GBP retreats from highs",
        "Pound strengthens on stronger-than-expected retail sales",
        "BOE holds rates; GBP dips on dovish commentary",
    ],
    "JPY": [
        "JPY strengthens as BOJ maintains ultra-loose policy",
        "Safe-haven flows lift JPY amid global risk-off sentiment",
        "Japan core CPI rises, fuelling BOJ taper speculation",
        "USD/JPY retreats as US yields slip; JPY bid",
        "BOJ intervention fears cap USD/JPY upside",
        "JPY weakens as risk appetite improves globally",
    ],
    "AUD": [
        "AUD rallies on strong China trade data",
        "RBA holds cash rate; AUD steady as traders digest statement",
        "Australian employment beats forecasts, AUD surges",
        "Iron ore prices slide, dragging AUD lower",
        "AUD/USD faces headwinds as commodity complex softens",
    ],
    "CAD": [
        "CAD gains on rising crude oil prices",
        "Bank of Canada signals pause; CAD mixed",
        "Canadian jobs data surprises higher, CAD firms",
        "Oil price decline puts CAD on the back foot",
        "CAD strengthens after hot Canadian CPI print",
    ],
    "NZD": [
        "RBNZ hikes rates; NZD jumps on hawkish tone",
        "NZD weakens as dairy prices fall at GDT auction",
        "New Zealand GDP beats estimates, NZD rallies",
        "RBNZ signals rate cuts ahead; NZD under pressure",
    ],
    "CHF": [
        "CHF firms as safe-haven demand returns",
        "SNB keeps rates unchanged; CHF steady",
        "Swiss CPI surprises higher, CHF ticks up",
        "CHF weakens as risk sentiment improves",
    ],
    "USD": [
        "USD strengthens on robust US non-farm payrolls",
        "Fed signals fewer rate cuts; USD surges",
        "US consumer confidence falls, weighing on USD",
        "Dollar softens as US inflation cools more than expected",
        "USD index climbs to multi-month high on hawkish Fed talk",
        "FOMC minutes flag recession risk; USD retreats",
    ],
    "XAU": [
        "Gold rallies as geopolitical tensions escalate",
        "XAUUSD climbs on weaker dollar and falling real yields",
        "Gold retreats as risk appetite recovers",
        "XAU/USD hits resistance at key technical level",
    ],
}

_DEFAULT_HEADLINES = [
    "Market participants await key central bank decision",
    "Risk sentiment shifts on global macro uncertainty",
    "Technical breakout attracts momentum buyers",
    "Consolidation continues as traders eye upcoming data",
    "Volatility spikes on unexpected geopolitical developments",
]

# Sentiment probability weights: (positive, neutral, negative)
_BASE_WEIGHTS = {
    "positive": 0.35,
    "neutral":  0.35,
    "negative": 0.30,
}

# Per-currency bias on the positive weight (positive shift = more bullish headlines)
_CURRENCY_BIAS = {
    "EUR": 0.03,
    "GBP": 0.02,
    "JPY": -0.03,
    "AUD": 0.02,
    "CAD": 0.01,
    "NZD": 0.01,
    "CHF": -0.01,
    "USD": 0.0,
    "XAU": 0.04,
}

# Sentiment score mapping
_SCORE_MAP = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_currencies(symbol: str) -> list[str]:
    """Pull the two 3-letter currency codes out of a 6-char FX symbol."""
    s = symbol.upper().replace("/", "").replace("_", "")
    if len(s) >= 6:
        return [s[:3], s[3:6]]
    return [s]


def _pick_headlines(symbol: str, rng: random.Random, n: int = 5) -> list[str]:
    """Pick n headlines weighted toward the symbol's currencies."""
    currencies = _extract_currencies(symbol)
    pool: list[str] = []
    for ccy in currencies:
        pool.extend(_HEADLINE_TEMPLATES.get(ccy, []))
    if len(pool) < n:
        pool.extend(_DEFAULT_HEADLINES)
    if len(pool) < n:
        pool.extend(_DEFAULT_HEADLINES)  # extend twice if very short
    return rng.sample(pool, min(n, len(pool)))


def _score_headline(headline: str, currency_bias: float, rng: random.Random) -> dict:
    """Assign a FinBERT-style sentiment label and score to a headline."""
    pos_w = max(0.05, _BASE_WEIGHTS["positive"] + currency_bias)
    neg_w = max(0.05, _BASE_WEIGHTS["negative"] - currency_bias * 0.5)
    neu_w = max(0.05, 1.0 - pos_w - neg_w)

    label = rng.choices(
        ["positive", "neutral", "negative"],
        weights=[pos_w, neu_w, neg_w],
        k=1,
    )[0]

    # Add sub-label magnitude noise
    base_score = _SCORE_MAP[label]
    noise = rng.uniform(-0.25, 0.25)
    raw_score = max(-1.0, min(1.0, base_score + noise))

    return {
        "headline": headline,
        "label": label,
        "score": round(raw_score, 4),
    }


def _composite_sentiment(individual_scores: list[dict]) -> float:
    """Weighted average of individual headline scores (recency-weighted)."""
    n = len(individual_scores)
    if n == 0:
        return 0.0
    weights = [1.0 + i * 0.15 for i in range(n)]  # later headlines slightly heavier
    total_w = sum(weights)
    composite = sum(s["score"] * w for s, w in zip(individual_scores, weights)) / total_w
    return round(max(-1.0, min(1.0, composite)), 4)


def _sentiment_bias_label(score: float) -> str:
    if score >= 0.4:
        return "strongly_bullish"
    if score >= 0.1:
        return "moderately_bullish"
    if score <= -0.4:
        return "strongly_bearish"
    if score <= -0.1:
        return "moderately_bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

def run_news_sentiment_nlp_agent(strategy: dict, metrics: dict | None = None) -> dict:
    symbol    = strategy.get("symbol", "EURUSD")
    p         = strategy.get("parameters", {})
    rsi_buy   = float(p.get("rsi_buy", 55.0) or 55.0)

    # Seeded determinism: symbol + current weekday so results shift daily
    weekday   = datetime.utcnow().weekday()  # 0=Mon … 6=Sun
    seed_str  = f"{symbol}{weekday}"
    seed      = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) & 0xFFFFFF
    rng       = random.Random(seed)

    currencies     = _extract_currencies(symbol)
    currency_bias  = sum(_CURRENCY_BIAS.get(c, 0.0) for c in currencies) / max(len(currencies), 1)

    headlines         = _pick_headlines(symbol, rng, n=5)
    individual_scores = [_score_headline(h, currency_bias, rng) for h in headlines]
    sentiment_score   = _composite_sentiment(individual_scores)
    bias_label        = _sentiment_bias_label(sentiment_score)

    is_bullish_strategy = rsi_buy > 52.0

    # Decision logic
    if is_bullish_strategy:
        if sentiment_score > 0.1:
            decision, risk_level, review_state = "approve", "low", "Approved"
            confidence = round(0.60 + min(abs(sentiment_score), 0.4) * 0.5, 3)
            reason = (
                f"Bullish sentiment detected for {symbol} (score {sentiment_score:+.2f}, "
                f"{bias_label.replace('_', ' ')}). Aligns with bullish strategy (rsi_buy={rsi_buy})."
            )
        elif sentiment_score >= -0.2:
            decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
            confidence = 0.55
            reason = (
                f"Neutral/weak sentiment for {symbol} (score {sentiment_score:+.2f}). "
                f"Insufficient bullish confirmation for strategy with rsi_buy={rsi_buy}. Retest later."
            )
        else:
            decision, risk_level, review_state = "reject", "high", "Rejected"
            confidence = round(0.65 + min(abs(sentiment_score), 0.4) * 0.4, 3)
            reason = (
                f"Bearish sentiment ({sentiment_score:+.2f}, {bias_label.replace('_', ' ')}) "
                f"contradicts bullish strategy direction for {symbol}. Avoid entry."
            )
    else:
        # Bearish strategy
        if sentiment_score < -0.1:
            decision, risk_level, review_state = "approve", "low", "Approved"
            confidence = round(0.60 + min(abs(sentiment_score), 0.4) * 0.5, 3)
            reason = (
                f"Bearish sentiment detected for {symbol} (score {sentiment_score:+.2f}, "
                f"{bias_label.replace('_', ' ')}). Aligns with bearish strategy (rsi_buy={rsi_buy})."
            )
        elif sentiment_score <= 0.2:
            decision, risk_level, review_state = "needs_retest", "medium", "Needs Retest"
            confidence = 0.55
            reason = (
                f"Neutral/weak sentiment for {symbol} (score {sentiment_score:+.2f}). "
                f"Insufficient bearish confirmation for strategy with rsi_buy={rsi_buy}. Retest later."
            )
        else:
            decision, risk_level, review_state = "reject", "high", "Rejected"
            confidence = round(0.65 + min(abs(sentiment_score), 0.4) * 0.4, 3)
            reason = (
                f"Bullish sentiment ({sentiment_score:+.2f}, {bias_label.replace('_', ' ')}) "
                f"contradicts bearish strategy direction for {symbol}. Avoid entry."
            )

    positive_count = sum(1 for s in individual_scores if s["label"] == "positive")
    negative_count = sum(1 for s in individual_scores if s["label"] == "negative")
    neutral_count  = sum(1 for s in individual_scores if s["label"] == "neutral")

    evidence = [
        f"Symbol: {symbol} | Strategy direction: {'bullish' if is_bullish_strategy else 'bearish'} (rsi_buy={rsi_buy})",
        f"Composite NLP sentiment score: {sentiment_score:+.2f} → {bias_label.replace('_', ' ')}",
        f"Headlines analysed: {len(individual_scores)} "
        f"({positive_count} positive, {neutral_count} neutral, {negative_count} negative)",
        f"Seed: hash({symbol!r} + weekday {weekday}) = {seed}  [deterministic within trading day]",
        f"Top headline: \"{individual_scores[0]['headline']}\" → {individual_scores[0]['label']} ({individual_scores[0]['score']:+.2f})",
    ]

    return {
        "agent": "News Sentiment NLP Agent",
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "evidence": evidence,
        "data": {
            "symbol": symbol,
            "sentiment_score": sentiment_score,
            "bias": bias_label,
            "headlines": [s["headline"] for s in individual_scores],
            "individual_scores": individual_scores,
            "positive_count": positive_count,
            "neutral_count": neutral_count,
            "negative_count": negative_count,
            "is_bullish_strategy": is_bullish_strategy,
            "rsi_buy": rsi_buy,
            "seed_weekday": weekday,
        },
        "review_state": review_state,
    }
