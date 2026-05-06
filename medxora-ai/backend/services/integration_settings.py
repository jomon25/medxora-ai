import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config import BACKEND_DATA_DIR

SETTINGS_PATH = Path(BACKEND_DATA_DIR) / "mission_integrations.json"
DEFAULT_LOCAL_MODELS = ["llama3", "qwen2.5"]


def _split_csv(raw_value: str) -> list[str]:
    return [item.strip() for item in str(raw_value or "").split(",") if item.strip()]


def _read_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
    return result


def _mask_secret(value: str) -> str:
    secret = str(value or "").strip()
    if not secret:
        return ""
    if len(secret) <= 10:
        return f"{secret[:3]}****"
    return f"{secret[:6]}****{secret[-2:]}"


def get_configured_api_keys() -> list[dict]:
    settings = _read_settings()
    configured: list[dict] = []
    seen_values: set[str] = set()

    def add_key(name: str, value: str):
        cleaned_value = str(value or "").strip()
        if not cleaned_value or cleaned_value in seen_values:
            return
        seen_values.add(cleaned_value)
        configured.append({
            "name": str(name or f"API Key {len(configured) + 1}").strip() or f"API Key {len(configured) + 1}",
            "value": cleaned_value,
        })

    for entry in settings.get("api_keys", []):
        if isinstance(entry, dict):
            add_key(entry.get("name", ""), entry.get("value", ""))

    for index, value in enumerate(_split_csv(os.getenv("MISSION_API_KEYS", "")), start=1):
        add_key(f"Mission API Key {index}", value)

    env_key_map = [
        ("Gemini Primary", os.getenv("GEMINI_API_KEY", "")),
        ("Gemini Backup", os.getenv("GEMINI_API_KEY_BACKUP", "")),
        ("Google API", os.getenv("GOOGLE_API_KEY", "")),
    ]
    for name, value in env_key_map:
        add_key(name, value)

    return configured


def get_configured_local_models() -> list[str]:
    settings = _read_settings()
    configured = []
    if isinstance(settings.get("local_models"), list):
        configured.extend(settings.get("local_models", []))
    configured.extend(_split_csv(os.getenv("MISSION_LOCAL_MODELS", "")))
    configured = _unique_strings(configured)
    return configured or list(DEFAULT_LOCAL_MODELS)


def save_integration_settings(api_keys: list[dict] | None = None, local_models: list[str] | None = None) -> dict:
    clean_keys = []
    for index, entry in enumerate(api_keys or [], start=1):
        if not isinstance(entry, dict):
            continue
        value = str(entry.get("value", "")).strip()
        if not value:
            continue
        clean_keys.append({
            "name": str(entry.get("name", f"API Key {index}")).strip() or f"API Key {index}",
            "value": value,
        })

    clean_models = _unique_strings(list(local_models or [])) or list(DEFAULT_LOCAL_MODELS)

    payload = {
        "api_keys": clean_keys,
        "local_models": clean_models,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    primary_key = clean_keys[0]["value"] if clean_keys else ""
    os.environ["GEMINI_API_KEY"] = primary_key
    os.environ["MISSION_API_KEYS"] = ",".join(item["value"] for item in clean_keys)
    os.environ["MISSION_LOCAL_MODELS"] = ",".join(clean_models)

    return get_integration_settings_payload(include_secret_values=False)


def get_integration_settings_payload(include_secret_values: bool = False) -> dict:
    keys = get_configured_api_keys()
    models = get_configured_local_models()

    api_keys = []
    for entry in keys:
        item = {
            "name": entry["name"],
            "masked_value": _mask_secret(entry["value"]),
        }
        if include_secret_values:
            item["value"] = entry["value"]
        api_keys.append(item)

    return {
        "api_keys": api_keys,
        "api_key_count": len(keys),
        "local_models": models,
        "local_model_count": len(models),
        "priority_order": [
            "Configured API keys",
            "Configured local models",
            "Mission prompt fallback",
        ],
    }
