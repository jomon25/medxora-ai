from services.gemini_service import GeminiService


def build_risk_prompt(strategy: dict):
    return f"""
You are the Google Gemini Risk Judge Agent for MedXora AI.

Analyze this trading strategy and produce a professional risk verdict.

Strategy:
{strategy}

Use these verdicts only:
- PRODUCTION_READY
- NEEDS_EVOLUTION
- OVERFIT_RISK
- REJECTED

Return ONLY valid JSON:
{{
  "verdict": "",
  "risk_score": 0,
  "robustness_score": 0,
  "main_strengths": [],
  "main_risks": [],
  "rejection_reason": "",
  "improvement_plan": [],
  "judge_friendly_explanation": ""
}}
"""


async def run_google_risk_judge_agent(strategy: dict):
    gemini = GeminiService()
    prompt = build_risk_prompt(strategy)
    result = gemini.generate_json(prompt)

    return {
        "agent": "Google Gemini Risk Judge Agent",
        "model": "gemini-2.5-flash",
        "result": result
    }
