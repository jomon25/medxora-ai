import os
import json
import asyncio
from google import genai


class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        self.client = genai.Client(api_key=api_key)

    def generate_text(self, prompt: str, model: str = "gemini-2.5-flash") -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text

    def generate_json(self, prompt: str, model: str = "gemini-2.5-flash") -> dict:
        response = self.client.models.generate_content(
            model=model,
            contents=prompt
        )

        text = response.text.strip()

        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()
        elif text.startswith("```"):
            text = text.replace("```", "").strip()

        try:
            return json.loads(text)
        except Exception:
            return {
                "error": "Gemini did not return valid JSON",
                "raw_response": response.text
            }


def get_gemini_service():
    return GeminiService()


async def gemini_generate_text(prompt: str, model: str = "gemini-2.5-flash") -> str:
    service = GeminiService()
    return await asyncio.to_thread(service.generate_text, prompt, model)


async def gemini_generate_json(prompt: str, model: str = "gemini-2.5-flash") -> dict:
    service = GeminiService()
    return await asyncio.to_thread(service.generate_json, prompt, model)


async def analyze_strategy(strategy_data=None, *args, **kwargs):
    """
    Backward-compatible function required by main.py.
    Used to analyze a trading strategy with Gemini.
    """
    prompt = f"""
You are the Strategy Analysis Agent for MedXora AI.

Analyze this trading strategy and return professional JSON.

Strategy data:
{strategy_data}

Extra args:
{args}

Extra kwargs:
{kwargs}

Return ONLY valid JSON:
{{
  "analysis_summary": "",
  "strategy_quality": "LOW | MEDIUM | HIGH",
  "strengths": [],
  "weaknesses": [],
  "risk_notes": [],
  "improvement_plan": [],
  "judge_friendly_explanation": ""
}}
"""
    return await gemini_generate_json(prompt)


async def meta_judge_agent_decisions(*args, **kwargs):
    """
    Backward-compatible function required by services.agent_orchestrator.
    Used to judge outputs from multiple agents.
    """
    prompt = f"""
You are the Meta Judge Agent for MedXora AI.

Analyze these agent decisions and return a professional JSON summary.

Args:
{args}

Kwargs:
{kwargs}

Return ONLY valid JSON:
{{
  "verdict": "OK",
  "confidence": 0.8,
  "strengths": [],
  "risks": [],
  "recommended_next_steps": [],
  "summary": ""
}}
"""
    return await gemini_generate_json(prompt)


async def generate_strategy_with_gemini(prompt: str):
    return await gemini_generate_json(prompt)


async def explain_with_gemini(prompt: str):
    return await gemini_generate_text(prompt)


async def call_gemini(prompt: str):
    return await gemini_generate_text(prompt)


async def suggest_improvement(strategy_data=None, analysis_data=None, *args, **kwargs):
    """
    Backward-compatible function required by main.py.
    Used to suggest improvements for a trading strategy.
    """
    prompt = f"""
You are the Strategy Improvement Agent for MedXora AI.

Suggest professional improvements for this trading strategy.

Strategy data:
{strategy_data}

Analysis data:
{analysis_data}

Extra args:
{args}

Extra kwargs:
{kwargs}

Return ONLY valid JSON:
{{
  "improvement_summary": "",
  "parameter_changes": [],
  "risk_improvements": [],
  "validation_steps": [],
  "mql5_notes": [],
  "expected_benefit": "",
  "judge_friendly_explanation": ""
}}
"""
    return await gemini_generate_json(prompt)
