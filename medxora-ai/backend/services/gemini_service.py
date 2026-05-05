import os
from dotenv import load_dotenv

load_dotenv()

_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


def _build_prompt(strategy: dict, metrics: dict | None = None) -> str:
    p = strategy.get("parameters", {})
    base = (
        f"Strategy: {strategy.get('name')}\n"
        f"Symbol: {strategy.get('symbol', 'EURUSD')} | Timeframe: {strategy.get('timeframe', 'M15')}\n"
        f"Fast EMA: {p.get('fast_ema')} | Slow EMA: {p.get('slow_ema')}\n"
        f"RSI Period: {p.get('rsi_period')} | Buy level: {p.get('rsi_buy')} | Sell level: {p.get('rsi_sell')}\n"
        f"Stop Loss: {p.get('stop_loss')} pts | Take Profit: {p.get('take_profit')} pts\n"
        f"Risk: {p.get('risk_percent')}%\n"
    )
    if metrics:
        base += (
            f"\nBacktest results:\n"
            f"Net Profit: ${metrics.get('net_profit', 'N/A')}\n"
            f"Win Rate: {metrics.get('win_rate', 'N/A')}%\n"
            f"Max Drawdown: {metrics.get('max_drawdown', 'N/A')}%\n"
            f"Profit Factor: {metrics.get('profit_factor', 'N/A')}\n"
            f"Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}\n"
        )
    return base


def analyze_strategy(strategy: dict, metrics: dict | None = None) -> str:
    """Ask Gemini to review strategy parameters and backtest results."""
    if not _GEMINI_KEY:
        return _fallback_analysis(strategy, metrics)

    try:
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are an expert algorithmic trading analyst. "
            "Review this EMA+RSI strategy and give a brief analysis (3-5 sentences): "
            "strengths, weaknesses, and one improvement suggestion.\n\n"
            + _build_prompt(strategy, metrics)
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[Gemini unavailable: {e}] " + _fallback_analysis(strategy, metrics)


def suggest_improvement(strategy: dict, metrics: dict) -> str:
    """Ask Gemini to suggest parameter improvements based on backtest results."""
    if not _GEMINI_KEY:
        return _fallback_suggestion(metrics)

    try:
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are an algorithmic trading optimizer. "
            "Based on this strategy's backtest results, suggest specific parameter changes "
            "to improve the profit factor and reduce drawdown. "
            "Be concise and specific (e.g. 'Increase fast EMA from 20 to 25').\n\n"
            + _build_prompt(strategy, metrics)
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[Gemini unavailable: {e}] " + _fallback_suggestion(metrics)


def _fallback_analysis(strategy: dict, metrics: dict | None) -> str:
    p = strategy.get("parameters", {})
    gap = (p.get("slow_ema", 50) - p.get("fast_ema", 20))
    rr = (p.get("take_profit", 400) / max(p.get("stop_loss", 200), 1))
    parts = [
        f"EMA gap is {gap} periods ({'good separation' if gap >= 20 else 'narrow — risk of whipsaws'}).",
        f"Reward/Risk ratio is {rr:.1f}x ({'acceptable' if rr >= 1.5 else 'too low'}).",
    ]
    if metrics:
        pf = metrics.get("profit_factor", 0)
        parts.append(f"Profit factor {pf:.2f} — {'strong' if pf >= 1.5 else 'needs improvement'}.")
    return " ".join(parts)


def _fallback_suggestion(metrics: dict) -> str:
    pf = metrics.get("profit_factor", 1)
    dd = metrics.get("max_drawdown", 20)
    tips = []
    if pf < 1.3:
        tips.append("Widen take profit or tighten entry conditions to improve profit factor.")
    if dd > 20:
        tips.append("Reduce stop loss size or risk percent to limit drawdown.")
    if not tips:
        tips.append("Strategy looks healthy. Consider testing on additional symbols.")
    return " ".join(tips)
