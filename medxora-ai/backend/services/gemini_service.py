import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

_STRATEGY_EXAMPLES = """
Examples:
1. Good strategy
{"fast_ema": 9, "slow_ema": 55, "rsi_buy": 57, "rsi_sell": 43, "stop_loss": 260, "take_profit": 520, "risk_percent": 1.0}
Outcome: profit_factor 1.71, drawdown 8.9, verdict approve.

2. Bad strategy
{"fast_ema": 8, "slow_ema": 12, "rsi_buy": 67, "rsi_sell": 31, "stop_loss": 700, "take_profit": 760, "risk_percent": 2.0}
Outcome: profit_factor 0.96, drawdown 24.0, verdict reject.

3. Borderline strategy
{"fast_ema": 11, "slow_ema": 28, "rsi_buy": 55, "rsi_sell": 45, "stop_loss": 300, "take_profit": 450, "risk_percent": 1.5}
Outcome: profit_factor 1.22, drawdown 13.5, verdict needs_improvement.
"""


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
            "\nBacktest results:\n"
            f"Net Profit: ${metrics.get('net_profit', 'N/A')}\n"
            f"Win Rate: {metrics.get('win_rate', 'N/A')}%\n"
            f"Max Drawdown: {metrics.get('max_drawdown', 'N/A')}%\n"
            f"Profit Factor: {metrics.get('profit_factor', 'N/A')}\n"
            f"Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}\n"
        )
    return base


def _extract_json(raw: str, fallback: dict) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        pass

    stripped = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass

    depth = 0
    start = -1
    for index, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = index
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(raw[start:index + 1])
                except Exception:
                    start = -1
    return fallback


def _generate_json(prompt: str, fallback: dict) -> dict:
    if not _GEMINI_KEY:
        return fallback

    try:
        import google.generativeai as genai

        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return _extract_json(response.text, fallback)
    except Exception as exc:
        result = dict(fallback)
        result.setdefault("meta", {})
        result["meta"]["fallback_reason"] = f"Gemini unavailable: {exc}"
        return result


def analyze_strategy(strategy: dict, metrics: dict | None = None) -> dict:
    fallback = _fallback_analysis(strategy, metrics)
    prompt = (
        "You are an expert algorithmic trading analyst. Review the strategy and return ONLY valid JSON.\n"
        + _STRATEGY_EXAMPLES
        + "\nReturn schema:\n"
        + json.dumps({
            "summary": "string",
            "verdict": "approve|reject|needs_improvement",
            "severity": "low|medium|high",
            "strengths": ["string"],
            "weaknesses": ["string"],
            "action_items": ["string"],
        })
        + "\n\n"
        + _build_prompt(strategy, metrics)
    )
    return _generate_json(prompt, fallback)


def suggest_improvement(strategy: dict, metrics: dict) -> dict:
    fallback = _fallback_suggestion(strategy, metrics)
    prompt = (
        "You are an algorithmic trading optimizer. Return ONLY valid JSON with specific, actionable mutations.\n"
        + _STRATEGY_EXAMPLES
        + "\nReturn schema:\n"
        + json.dumps({
            "summary": "string",
            "priority": "low|medium|high",
            "parameter_changes": [
                {"parameter": "fast_ema", "current": 10, "suggested": 12, "reason": "string"}
            ],
            "expected_impact": ["string"],
        })
        + "\n\n"
        + _build_prompt(strategy, metrics)
    )
    return _generate_json(prompt, fallback)


def meta_judge_agent_decisions(strategy: dict, metrics: dict | None, agent_decisions: dict) -> dict:
    fallback = _fallback_meta_judge(strategy, metrics, agent_decisions)
    prompt = (
        "You are the MedXora meta-agent judge. Given all agent opinions, return ONLY valid JSON.\n"
        + _STRATEGY_EXAMPLES
        + "\nReturn schema:\n"
        + json.dumps({
            "verdict": "approve|reject|needs_evolution|needs_retest",
            "confidence": 0.72,
            "summary": "string",
            "top_conflicts": ["string"],
            "recommended_parameter_change": {
                "parameter": "fast_ema",
                "current": 10,
                "suggested": 12,
                "reason": "string",
            },
        })
        + "\n\nStrategy:\n"
        + _build_prompt(strategy, metrics)
        + "\nAgent decisions:\n"
        + json.dumps(agent_decisions, default=str)[:10000]
    )
    return _generate_json(prompt, fallback)


def _fallback_analysis(strategy: dict, metrics: dict | None) -> dict:
    p = strategy.get("parameters", {})
    gap = (p.get("slow_ema", 50) - p.get("fast_ema", 20))
    rr = (p.get("take_profit", 400) / max(p.get("stop_loss", 200), 1))
    strengths = []
    weaknesses = []
    actions = []

    if gap >= 20:
        strengths.append(f"EMA gap is {gap}, which provides decent trend separation.")
    else:
        weaknesses.append(f"EMA gap is only {gap}, so whipsaw risk is elevated.")
        actions.append("Widen the EMA gap to reduce chop sensitivity.")

    if rr >= 1.5:
        strengths.append(f"Reward/risk ratio is {rr:.1f}x, which meets the baseline.")
    else:
        weaknesses.append(f"Reward/risk ratio is only {rr:.1f}x.")
        actions.append("Increase take profit or reduce stop loss to restore a stronger reward/risk profile.")

    verdict = "approve"
    severity = "low"
    if metrics:
        pf = float(metrics.get("profit_factor", 0) or 0)
        dd = float(metrics.get("max_drawdown", 0) or 0)
        if pf < 1.2 or dd > 15:
            verdict = "needs_improvement"
            severity = "medium"
            weaknesses.append(f"Observed profit factor {pf:.2f} and drawdown {dd:.1f}% still need improvement.")
            actions.append("Reduce drawdown and improve profit factor before live consideration.")

    if not actions:
        actions.append("Retest the strategy on additional symbols before live rollout.")

    return {
        "summary": " ".join(strengths[:1] + weaknesses[:1]) or "Strategy review completed.",
        "verdict": verdict,
        "severity": severity,
        "strengths": strengths or ["Core EMA/RSI structure is understandable and testable."],
        "weaknesses": weaknesses or ["No major structural issue detected in the fallback review."],
        "action_items": actions,
    }


def _fallback_suggestion(strategy: dict, metrics: dict) -> dict:
    p = strategy.get("parameters", {})
    changes = []
    impacts = []

    pf = float(metrics.get("profit_factor", 1) or 1)
    dd = float(metrics.get("max_drawdown", 20) or 20)
    fast = p.get("fast_ema", 10)
    slow = p.get("slow_ema", 50)

    if pf < 1.3:
        changes.append({
            "parameter": "slow_ema",
            "current": slow,
            "suggested": slow + 5,
            "reason": "A slightly wider EMA spread can reduce noisy entries and lift profit factor.",
        })
        impacts.append("Cleaner entries may improve profit factor.")
    if dd > 20:
        changes.append({
            "parameter": "risk_percent",
            "current": p.get("risk_percent", 1.0),
            "suggested": max(0.5, round(float(p.get("risk_percent", 1.0) or 1.0) - 0.25, 2)),
            "reason": "Reducing per-trade risk directly lowers portfolio drawdown pressure.",
        })
        impacts.append("Lower position risk should improve drawdown stability.")
    if not changes:
        changes.append({
            "parameter": "fast_ema",
            "current": fast,
            "suggested": fast + 1,
            "reason": "A minor timing adjustment is the least disruptive next mutation.",
        })
        impacts.append("Small timing changes can refine entry quality without changing the whole strategy.")

    return {
        "summary": "Target the weakest parameter first instead of mutating everything at once.",
        "priority": "high" if dd > 20 or pf < 1.2 else "medium",
        "parameter_changes": changes,
        "expected_impact": impacts,
    }


def _fallback_meta_judge(strategy: dict, metrics: dict | None, agent_decisions: dict) -> dict:
    approve = 0
    reject = 0
    needs_evolution = 0
    needs_retest = 0
    for decision in agent_decisions.values():
        verdict = decision.get("decision")
        if verdict == "approve":
            approve += 1
        elif verdict == "reject":
            reject += 1
        elif verdict == "needs_evolution":
            needs_evolution += 1
        else:
            needs_retest += 1

    params = strategy.get("parameters", {})
    if reject >= max(2, approve):
        verdict = "reject"
        summary = "The risk-facing agents are not comfortable with this setup yet."
    elif needs_evolution > approve:
        verdict = "needs_evolution"
        summary = "The setup has promise, but too many agents are asking for parameter changes."
    elif needs_retest >= approve:
        verdict = "needs_retest"
        summary = "The decision spread is inconclusive, so more validation is the safer path."
    else:
        verdict = "approve"
        summary = "Most agents agree the setup is structurally acceptable."

    return {
        "verdict": verdict,
        "confidence": 0.7,
        "summary": summary,
        "top_conflicts": [
            f"approve={approve}",
            f"reject={reject}",
            f"needs_evolution={needs_evolution}",
            f"needs_retest={needs_retest}",
        ],
        "recommended_parameter_change": {
            "parameter": "slow_ema",
            "current": params.get("slow_ema"),
            "suggested": (params.get("slow_ema") or 50) + 5,
            "reason": "A slightly wider EMA spread is the safest general-purpose mutation when agents disagree.",
        },
    }
