from services.gemini_service import GeminiService


def build_mission_prompt(mission: str, symbol: str, timeframe: str, risk_profile: str, memory_context: dict):
    return f"""
You are the Google Gemini Mission Planner Agent for MedXora AI.

MedXora AI is an autonomous MetaTrader 5 trading strategy engine.
It generates strategies, validates risk, prepares MQL5 Expert Advisor logic,
stores memory in MongoDB Atlas, and evolves strategies over time.

User mission:
{mission}

Symbol:
{symbol}

Timeframe:
{timeframe}

Risk profile:
{risk_profile}

MongoDB memory context:
{memory_context}

Return ONLY valid JSON.

Required JSON:
{{
  "mission_title": "",
  "mission_summary": "",
  "symbol": "{symbol}",
  "timeframe": "{timeframe}",
  "risk_profile": "{risk_profile}",
  "strategy_type": "",
  "selected_agents": [],
  "market_assumption": "",
  "indicators": [],
  "entry_rules": [],
  "exit_rules": [],
  "risk_rules": [],
  "validation_plan": [],
  "mql5_design_notes": [],
  "rejection_rules": [],
  "agent_timeline": [],
  "mongodb_memory_to_save": "",
  "judge_demo_summary": ""
}}
"""


async def run_google_mission_planner_agent(mission: str, symbol: str, timeframe: str, risk_profile: str, memory_context: dict):
    gemini = GeminiService()
    prompt = build_mission_prompt(mission, symbol, timeframe, risk_profile, memory_context)
    result = gemini.generate_json(prompt)

    return {
        "agent": "Google Gemini Mission Planner Agent",
        "model": "gemini-2.5-flash",
        "result": result
    }
