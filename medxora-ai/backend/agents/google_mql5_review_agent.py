from services.gemini_service import GeminiService


def build_mql5_review_prompt(strategy: dict):
    return f"""
You are the Google Gemini MQL5 Review Agent for MedXora AI.

Review the strategy design before MQL5 Expert Advisor generation.

Strategy:
{strategy}

Check for:
- missing risk controls
- look-ahead bias
- missing spread filter
- missing session filter
- bad lot sizing
- unsafe trade logic
- missing stop loss
- MQL5 implementation risks

Return ONLY valid JSON:
{{
  "compile_risk": "LOW | MEDIUM | HIGH",
  "safe_to_generate_mql5": true,
  "critical_issues": [],
  "recommended_fixes": [],
  "mql5_design_checklist": [],
  "professional_summary": ""
}}
"""


async def run_google_mql5_review_agent(strategy: dict):
    gemini = GeminiService()
    prompt = build_mql5_review_prompt(strategy)
    result = gemini.generate_json(prompt)

    return {
        "agent": "Google Gemini MQL5 Review Agent",
        "model": "gemini-2.5-flash",
        "result": result
    }
