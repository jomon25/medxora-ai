ALLOWED_TIMEFRAMES = ["M1", "M15", "H1", "H4", "D1", "W1"]


def normalize_timeframe(value: str | None, default: str = "M15") -> str:
    candidate = (value or default).strip().upper()
    if candidate not in ALLOWED_TIMEFRAMES:
        raise ValueError(
            f"Unsupported timeframe '{value}'. Allowed values: {', '.join(ALLOWED_TIMEFRAMES)}"
        )
    return candidate
