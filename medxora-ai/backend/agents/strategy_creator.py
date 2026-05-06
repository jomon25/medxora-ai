import json
import os
import random
import re
import urllib.error
import urllib.request
import uuid
from services.integration_settings import get_configured_api_keys, get_configured_local_models
from services.timeframes import normalize_timeframe

STRATEGY_TYPES = [
    "ema_rsi",
    "breakout",
    "bollinger_mean_reversion",
    "macd_crossover",
    "supertrend",
    "adx_trend_filter",
    "donchian_breakout",
    "multi_tf_ema_rsi",
    "news_avoidance",
    # New strategy types (v2)
    "ichimoku",
    "stochastic_rsi",
    "vwap_deviation",
    "pivot_points",
    "grid_trading",
]

STRATEGY_PREFIXES = {
    "ema_rsi":                 "EMA_RSI",
    "breakout":                "BRKOUT",
    "bollinger_mean_reversion":"BB_REV",
    "macd_crossover":          "MACD_X",
    "supertrend":              "SUPERT",
    "adx_trend_filter":        "ADX_TF",
    "donchian_breakout":       "DONCH",
    "multi_tf_ema_rsi":        "MTF_EMA",
    "news_avoidance":          "NEWS_AV",
    # New
    "ichimoku":                "ICHI",
    "stochastic_rsi":          "SRSI",
    "vwap_deviation":          "VWAP",
    "pivot_points":            "PIVOT",
    "grid_trading":            "GRID",
}


def _ema_rsi_params():
    fast = random.randint(10, 30)
    slow = random.randint(fast + 15, fast + 70)
    return {
        "fast_ema":    fast,
        "slow_ema":    slow,
        "rsi_period":  14,
        "rsi_buy":     random.randint(52, 60),
        "rsi_sell":    random.randint(40, 48),
        "stop_loss":   random.randint(200, 500),
        "take_profit": random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _breakout_params():
    return {
        "breakout_period":  random.randint(10, 30),
        "atr_period":       14,
        "atr_multiplier":   round(random.uniform(1.5, 3.0), 1),
        "volume_filter":    random.choice([True, False]),
        "stop_loss":        random.randint(200, 600),
        "take_profit":      random.randint(400, 1200),
        "risk_percent":     1.0,
    }


def _bollinger_params():
    return {
        "bb_period":       random.randint(14, 25),
        "bb_deviation":    round(random.uniform(1.5, 2.5), 1),
        "rsi_period":      14,
        "rsi_oversold":    random.randint(25, 35),
        "rsi_overbought":  random.randint(65, 75),
        "stop_loss":       random.randint(150, 400),
        "take_profit":     random.randint(300, 800),
        "risk_percent":    1.0,
    }


def _macd_params():
    fast = random.randint(8, 14)
    slow = random.randint(fast + 10, fast + 20)
    signal = random.randint(7, 11)
    return {
        "macd_fast":    fast,
        "macd_slow":    slow,
        "macd_signal":  signal,
        "rsi_period":   14,
        "rsi_filter":   random.randint(45, 55),
        "stop_loss":    random.randint(200, 500),
        "take_profit":  random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _supertrend_params():
    return {
        "atr_period":     random.randint(7, 14),
        "atr_multiplier": round(random.uniform(2.0, 4.0), 1),
        "ema_filter":     random.randint(100, 200),
        "stop_loss":      random.randint(200, 600),
        "take_profit":    random.randint(400, 1200),
        "risk_percent":   1.0,
    }


def _adx_params():
    fast = random.randint(8, 20)
    slow = random.randint(fast + 10, fast + 50)
    return {
        "adx_period":   random.randint(10, 20),
        "adx_threshold": random.randint(20, 30),
        "fast_ema":     fast,
        "slow_ema":     slow,
        "stop_loss":    random.randint(200, 500),
        "take_profit":  random.randint(400, 1000),
        "risk_percent": 1.0,
    }


def _donchian_params():
    return {
        "donchian_period":  random.randint(15, 30),
        "atr_period":       14,
        "breakout_confirm": random.randint(1, 3),
        "stop_loss":        random.randint(250, 600),
        "take_profit":      random.randint(500, 1200),
        "risk_percent":     1.0,
    }


def _multi_tf_params():
    fast = random.randint(10, 25)
    slow = random.randint(fast + 15, fast + 60)
    return {
        "fast_ema":          fast,
        "slow_ema":          slow,
        "higher_tf_ema":     random.randint(50, 100),
        "higher_timeframe":  random.choice(["H4", "D1"]),
        "rsi_period":        14,
        "rsi_buy":           random.randint(52, 60),
        "rsi_sell":          random.randint(40, 48),
        "stop_loss":         random.randint(200, 500),
        "take_profit":       random.randint(400, 1000),
        "risk_percent":      1.0,
    }


def _news_avoidance_params():
    fast = random.randint(10, 25)
    slow = random.randint(fast + 15, fast + 60)
    return {
        "fast_ema":          fast,
        "slow_ema":          slow,
        "rsi_period":        14,
        "rsi_buy":           random.randint(52, 60),
        "rsi_sell":          random.randint(40, 48),
        "news_pause_minutes": random.choice([30, 60, 120]),
        "avoid_friday_close": True,
        "stop_loss":         random.randint(200, 500),
        "take_profit":       random.randint(400, 1000),
        "risk_percent":      1.0,
    }


def _ichimoku_params():
    return {
        "tenkan_period":   random.randint(7, 12),
        "kijun_period":    random.randint(22, 30),
        "senkou_b_period": random.randint(48, 56),
        "displacement":    26,
        "stop_loss":       random.randint(200, 600),
        "take_profit":     random.randint(400, 1200),
        "risk_percent":    1.0,
    }


def _stochastic_rsi_params():
    return {
        "stoch_period":     random.randint(12, 16),
        "stoch_smooth_k":   random.randint(2, 4),
        "stoch_smooth_d":   random.randint(2, 4),
        "rsi_period":       14,
        "oversold":         random.randint(20, 30),
        "overbought":       random.randint(70, 80),
        "stop_loss":        random.randint(150, 400),
        "take_profit":      random.randint(300, 800),
        "risk_percent":     1.0,
    }


def _vwap_deviation_params():
    return {
        "vwap_period":      random.randint(14, 25),
        "deviation_bands":  round(random.uniform(1.5, 2.5), 1),
        "rsi_period":       14,
        "rsi_confirm":      random.randint(45, 55),
        "stop_loss":        random.randint(150, 400),
        "take_profit":      random.randint(300, 800),
        "risk_percent":     1.0,
    }


def _pivot_points_params():
    return {
        "pivot_type":       random.choice(["standard", "fibonacci", "camarilla"]),
        "sr_levels":        random.choice([2, 3]),
        "ema_filter":       random.randint(50, 200),
        "rsi_period":       14,
        "rsi_confirm":      random.randint(45, 55),
        "stop_loss":        random.randint(200, 500),
        "take_profit":      random.randint(400, 1000),
        "risk_percent":     1.0,
    }


def _grid_trading_params():
    return {
        "grid_size_pips":   random.randint(15, 40),
        "grid_levels":      random.randint(3, 8),
        "base_lot":         round(random.uniform(0.01, 0.05), 2),
        "max_grid_dd_pct":  random.randint(10, 20),
        "take_profit":      random.randint(30, 80),
        "stop_loss":        random.randint(200, 500),
        "risk_percent":     0.5,
    }


PARAM_BUILDERS = {
    "ema_rsi":                 _ema_rsi_params,
    "breakout":                _breakout_params,
    "bollinger_mean_reversion":_bollinger_params,
    "macd_crossover":          _macd_params,
    "supertrend":              _supertrend_params,
    "adx_trend_filter":        _adx_params,
    "donchian_breakout":       _donchian_params,
    "multi_tf_ema_rsi":        _multi_tf_params,
    "news_avoidance":          _news_avoidance_params,
    # New
    "ichimoku":                _ichimoku_params,
    "stochastic_rsi":          _stochastic_rsi_params,
    "vwap_deviation":          _vwap_deviation_params,
    "pivot_points":            _pivot_points_params,
    "grid_trading":            _grid_trading_params,
}


def _sanitize_strategy_name(name: str | None, strategy_type: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_ -]+", "", str(name or "")).strip().replace(" ", "_")
    cleaned = cleaned[:36].strip("_")
    if cleaned:
        return cleaned.upper()
    prefix = STRATEGY_PREFIXES[strategy_type]
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"


def _extract_preferred_name(mission_brief: str | None) -> str | None:
    if not mission_brief:
        return None
    match = re.search(r"Preferred strategy name:\s*([^\.]+)", mission_brief, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_strategy_description(mission_brief: str | None) -> str:
    if not mission_brief:
        return ""
    match = re.search(r"Strategy description:\s*([^\.]+)", mission_brief, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return mission_brief.strip()


def _normalize_ai_strategy(payload: dict, timeframe: str, preferred_name: str | None = None) -> dict | None:
    strategy_type = payload.get("strategy_type")
    if strategy_type not in PARAM_BUILDERS:
        return None
    params = payload.get("parameters")
    if not isinstance(params, dict):
        return None
    return {
        "name": _sanitize_strategy_name(preferred_name or payload.get("name"), strategy_type),
        "symbol": "EURUSD",
        "timeframe": timeframe,
        "strategy_type": strategy_type,
        "parameters": params,
    }


def _build_strategy_prompt(timeframe: str, mission_brief: str | None, preferred_name: str | None) -> str:
    allowed_types = ", ".join(STRATEGY_TYPES)
    return f"""You are a quantitative FX strategy designer.
Create one EURUSD strategy for timeframe {timeframe}.
Mission brief: {mission_brief or 'Create a robust EURUSD strategy.'}
Preferred strategy name: {preferred_name or 'auto-generate if needed'}

Return ONLY valid JSON:
{{
  "name": "strategy name",
  "symbol": "EURUSD",
  "timeframe": "{timeframe}",
  "strategy_type": "one of [{allowed_types}]",
  "parameters": {{
    "stop_loss": 250,
    "take_profit": 500,
    "risk_percent": 1.0
  }}
}}

Rules:
- strategy_type must be one of: {allowed_types}
- parameters must match the chosen strategy type
- risk_percent must stay at or below 1.0
- prefer realistic, conservative values suitable for EURUSD
"""


def _generate_strategy_with_gemini(prompt: str, timeframe: str, preferred_name: str | None = None) -> tuple[dict | None, list[dict]]:
    attempts = []
    api_keys = get_configured_api_keys()
    if not api_keys:
        attempts.append({
            "provider": "gemini_api",
            "target": "none",
            "status": "skipped",
            "detail": "No configured API keys were available.",
        })
        return None, attempts

    for index, entry in enumerate(api_keys, start=1):
        api_key = entry.get("value", "").strip()
        display_name = entry.get("name") or f"API Key {index}"
        if not api_key:
            continue
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt, request_options={"timeout": 30})
            raw = getattr(response, "text", "") or ""
            payload = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            strategy = _normalize_ai_strategy(payload, timeframe, preferred_name)
            if strategy:
                attempts.append({
                    "provider": "gemini_api",
                    "target": display_name,
                    "status": "success",
                    "detail": "Strategy generated successfully.",
                })
                strategy["generation_source"] = f"gemini_api:{display_name}"
                return strategy, attempts
            attempts.append({
                "provider": "gemini_api",
                "target": display_name,
                "status": "failed",
                "detail": "Returned payload did not match a supported strategy schema.",
            })
        except Exception as exc:
            attempts.append({
                "provider": "gemini_api",
                "target": display_name,
                "status": "failed",
                "detail": str(exc),
            })

    return None, attempts


def _generate_strategy_with_local_model(prompt: str, timeframe: str, preferred_name: str | None = None) -> tuple[dict | None, list[dict]]:
    attempts = []
    model_names = get_configured_local_models()
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    for model_name in model_names:
        try:
            request = urllib.request.Request(
                f"{base_url}/api/generate",
                data=json.dumps({
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            raw = str(payload.get("response", "")).strip()
            if raw.startswith("```"):
                raw = raw.replace("```json", "").replace("```", "").strip()
            strategy_payload = json.loads(raw)
            strategy = _normalize_ai_strategy(strategy_payload, timeframe, preferred_name)
            if strategy:
                strategy["generation_source"] = f"local_model:{model_name}"
                attempts.append({
                    "provider": "local_model",
                    "target": model_name,
                    "status": "success",
                    "detail": "Strategy generated successfully.",
                })
                return strategy, attempts
            attempts.append({
                "provider": "local_model",
                "target": model_name,
                "status": "failed",
                "detail": "Returned payload did not match a supported strategy schema.",
            })
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
            attempts.append({
                "provider": "local_model",
                "target": model_name,
                "status": "failed",
                "detail": str(exc),
            })
            continue
    return None, attempts


def generate_strategy(timeframe: str = "M15", strategy_type: str = None, mission_brief: str | None = None, preferred_name: str | None = None):
    timeframe = normalize_timeframe(timeframe)
    preferred_name = preferred_name or _extract_preferred_name(mission_brief)
    attempts = []

    prompt = _build_strategy_prompt(timeframe, _extract_strategy_description(mission_brief), preferred_name)
    gemini_strategy, gemini_attempts = _generate_strategy_with_gemini(prompt, timeframe, preferred_name)
    attempts.extend(gemini_attempts)
    if gemini_strategy:
        gemini_strategy["generation_attempts"] = attempts
        return gemini_strategy

    local_strategy, local_attempts = _generate_strategy_with_local_model(prompt, timeframe, preferred_name)
    attempts.extend(local_attempts)
    if local_strategy:
        local_strategy["generation_attempts"] = attempts
        return local_strategy

    if strategy_type not in PARAM_BUILDERS:
        strategy_type = random.choice(STRATEGY_TYPES)
    name = _sanitize_strategy_name(preferred_name, strategy_type)
    params = PARAM_BUILDERS[strategy_type]()
    return {
        "name": name,
        "symbol": "EURUSD",
        "timeframe": timeframe,
        "strategy_type": strategy_type,
        "parameters": params,
        "generation_source": "mission_prompt_fallback",
        "generation_attempts": attempts + [{
            "provider": "mission_prompt",
            "target": "built_in_fallback",
            "status": "success",
            "detail": "Used the internal mission prompt fallback after AI providers were unavailable.",
        }],
    }
