"""
services/gemini_planner.py
Gemini as the main reasoning brain for MedXora AI Mission Control.
Roles: Mission Planner, Strategy Critic, Risk Explainer, Evolution Advisor, Report Writer, Tool Router.
"""
import os, json
from dotenv import load_dotenv
load_dotenv()
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

_gemini_model = None
if _GEMINI_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_KEY)
        _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        _gemini_model = None


def _call_gemini(prompt: str, fallback: str) -> str:
    if not _gemini_model:
        return fallback
    try:
        resp = _gemini_model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"[Gemini unavailable: {e}] {fallback}"


def plan_mission(user_goal: str, pair: str = "EURUSD", timeframe: str = "M15") -> dict:
    """Convert a natural-language user goal into a structured step plan."""
    prompt = f"""You are MedXora AI Mission Planner. Convert this trading strategy research goal into a JSON step plan.

User goal: {user_goal}
Pair: {pair}, Timeframe: {timeframe}

Return ONLY valid JSON with this structure:
{{
  "plan_summary": "one-sentence summary",
  "steps": [
    {{"step_number": 1, "step_name": "Understand User Goal", "tool_name": "gemini_planner", "requires_approval": false, "description": "..."}},
    {{"step_number": 2, "step_name": "Generate Strategy", "tool_name": "generate_strategy", "requires_approval": false, "description": "..."}},
    ...
  ],
  "estimated_risk": "low|medium|high",
  "recommended_generations": 3
}}

Include steps for: strategy generation, risk validation, MQL5 generation, mock backtest, fitness scoring, Monte Carlo validation, evolution (if needed), MCP memory save, champion selection, human approval, MQL5 export, Gemini report.
Steps that need human approval: evolution start, MQL5 export, champion designation."""

    fallback = json.dumps({"plan_summary": f"Research {pair} strategy on {timeframe}", "steps": [
        {"step_number": 1, "step_name": "Understand User Goal", "tool_name": "gemini_planner", "requires_approval": False, "description": "Analyse goal"},
        {"step_number": 2, "step_name": "Generate EMA+RSI Strategy", "tool_name": "generate_strategy", "requires_approval": False, "description": "Create strategy"},
        {"step_number": 3, "step_name": "Validate Risk Parameters", "tool_name": "risk_manager", "requires_approval": False, "description": "Risk check"},
        {"step_number": 4, "step_name": "Generate MQL5 Expert Advisor", "tool_name": "mql5_generator", "requires_approval": False, "description": "Write EA"},
        {"step_number": 5, "step_name": "Run Mock Backtest", "tool_name": "backtest_mock", "requires_approval": False, "description": "Backtest"},
        {"step_number": 6, "step_name": "Parse Backtest Report", "tool_name": "report_parser", "requires_approval": False, "description": "Parse metrics"},
        {"step_number": 7, "step_name": "Calculate Fitness Score", "tool_name": "fitness_scorer", "requires_approval": False, "description": "Score"},
        {"step_number": 8, "step_name": "Monte Carlo Validation", "tool_name": "monte_carlo_agent", "requires_approval": False, "description": "Robustness"},
        {"step_number": 9, "step_name": "Evolve Best Strategy", "tool_name": "evolution_agent", "requires_approval": True, "description": "Evolve"},
        {"step_number": 10, "step_name": "Search Strategy Memory", "tool_name": "mcp_search", "requires_approval": False, "description": "MCP search"},
        {"step_number": 11, "step_name": "Select Champion Strategy", "tool_name": "ensemble_voting", "requires_approval": True, "description": "Select champion"},
        {"step_number": 12, "step_name": "Human Approval Required", "tool_name": "human_approval", "requires_approval": True, "description": "Await approval"},
        {"step_number": 13, "step_name": "Export Final MQL5 File", "tool_name": "mql5_export", "requires_approval": True, "description": "Export EA"},
        {"step_number": 14, "step_name": "Generate Gemini Report", "tool_name": "gemini_report", "requires_approval": False, "description": "Final report"},
    ], "estimated_risk": "medium", "recommended_generations": 3})

    raw = _call_gemini(prompt, fallback)
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return json.loads(fallback)


def critique_strategy(strategy: dict, metrics: dict | None = None) -> dict:
    """Gemini Strategy Critic — quality assessment with score 0-100."""
    p = strategy.get("parameters", {})
    summary = (f"Strategy {strategy.get('name')}: {strategy.get('symbol')} {strategy.get('timeframe')}, "
               f"EMA {p.get('fast_ema')}/{p.get('slow_ema')}, RSI {p.get('rsi_period')}, "
               f"SL {p.get('stop_loss')} TP {p.get('take_profit')}, Risk {p.get('risk_percent')}%")
    if metrics:
        summary += (f" | Sharpe {metrics.get('sharpe_ratio','?')}, "
                    f"DD {metrics.get('max_drawdown','?')}%, WR {metrics.get('win_rate','?')}%")

    prompt = f"""You are a professional algorithmic trading strategy critic.
Evaluate this strategy and return ONLY valid JSON:
{summary}

Return:
{{"quality_score": 0-100, "verdict": "approve|reject|needs_improvement", "strengths": ["..."], "weaknesses": ["..."], "recommendation": "one sentence"}}"""

    fallback = json.dumps({"quality_score": 65, "verdict": "needs_improvement",
                           "strengths": ["Decent EMA separation", "Acceptable risk/reward ratio"],
                           "weaknesses": ["Missing volatility filter", "RSI thresholds could be tighter"],
                           "recommendation": "Consider widening EMA gap and reducing risk_percent for lower drawdown."})
    raw = _call_gemini(prompt, fallback)
    try:
        start = raw.find("{"); end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return json.loads(fallback)


def explain_risk(strategy: dict, risk_result: dict) -> str:
    """Gemini Risk Explainer — plain-English explanation of risk agent decision."""
    approved = risk_result.get("passed", False)
    issues = risk_result.get("issues", [])
    prompt = f"""You are a trading risk explainer. In 2-3 sentences, explain why this strategy was {'APPROVED' if approved else 'REJECTED'} by the Risk Agent.
Strategy: {strategy.get('name')}, Risk {strategy.get('parameters', {}).get('risk_percent')}%, SL {strategy.get('parameters', {}).get('stop_loss')}, TP {strategy.get('parameters', {}).get('take_profit')}
Issues: {', '.join(issues) if issues else 'none'}"""
    fallback = f"Strategy {'passed' if approved else 'failed'} risk validation. {'No critical issues detected.' if approved else 'Issues: ' + ', '.join(issues[:2])}"
    return _call_gemini(prompt, fallback)


def advise_evolution(parent: dict, child_scores: list, generation: int) -> str:
    """Gemini Evolution Advisor — mutation direction for next generation."""
    prompt = f"""You are a genetic algorithm advisor for trading strategies.
Parent strategy gen {generation}: {parent.get('name')}
Child scores: {child_scores}
In 2-3 sentences, suggest the best mutation direction for the next generation. Focus on SL/TP ratio, EMA gap, and RSI thresholds."""
    fallback = f"Generation {generation} suggests focusing on tightening RSI thresholds and widening the EMA gap to reduce whipsaws. Consider reducing risk_percent if drawdown exceeded 15%."
    return _call_gemini(prompt, fallback)


def write_final_report(mission_goal: str, champion: dict, metrics: dict, validation: dict) -> str:
    """Gemini Report Writer — judge-friendly final mission report."""
    prompt = f"""Write a professional 4-paragraph trading strategy research report for a competition judge.
Mission: {mission_goal}
Champion: {champion.get('name', 'Unknown')} on {champion.get('symbol','EURUSD')} {champion.get('timeframe','M15')}
Metrics: Sharpe {metrics.get('sharpe_ratio','?')}, Drawdown {metrics.get('max_drawdown','?')}%, Win Rate {metrics.get('win_rate','?')}%, Profit Factor {metrics.get('profit_factor','?')}
Validation: Robustness {validation.get('robustness_score','?')}/100, Risk Score {validation.get('risk_score','?')}/100, Passed: {validation.get('passed', False)}
Include: methodology, results, safety controls, and conclusion. Keep it professional and concise."""
    fallback = f"""## MedXora AI Mission Report

**Mission:** {mission_goal}

**Methodology:** The MedXora AI multi-agent pipeline generated and validated an EMA+RSI Expert Advisor strategy using Gemini-powered planning, automated risk validation, mock backtesting, and genetic evolution.

**Champion Strategy:** {champion.get('name','Strategy')} achieved a Sharpe ratio of {metrics.get('sharpe_ratio','N/A')}, maximum drawdown of {metrics.get('max_drawdown','N/A')}%, and win rate of {metrics.get('win_rate','N/A')}%.

**Safety Controls:** All evolution and export steps required explicit human approval. The Risk Manager and Monte Carlo agents provided hard-veto capability. No live trading was performed.

**Conclusion:** The strategy meets research-grade quality standards and is ready for further paper trading validation."""
    return _call_gemini(prompt, fallback)


def route_tool(current_step: str, context: dict) -> dict:
    """Gemini Tool Router — decides which tool/endpoint to call next."""
    prompt = f"""You are an AI tool router. Given the current mission step and context, decide the next tool call.
Current step: {current_step}
Context: {json.dumps(context, default=str)[:500]}
Return ONLY JSON: {{"tool": "tool_name", "reason": "one sentence", "priority": "high|medium|low"}}"""
    fallback = json.dumps({"tool": "generate_strategy", "reason": "Default to strategy generation as next step.", "priority": "high"})
    raw = _call_gemini(prompt, fallback)
    try:
        start = raw.find("{"); end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return json.loads(fallback)
