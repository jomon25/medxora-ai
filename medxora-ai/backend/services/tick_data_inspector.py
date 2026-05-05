from __future__ import annotations

from pathlib import Path


def inspect_tick_data_file(path: str) -> dict:
    file_path = Path(path)
    if not path:
        return {
            "status": "missing",
            "detail": "MT5_TICK_DATA_PATH not configured",
            "path": "",
        }

    if not file_path.exists():
        return {
            "status": "missing",
            "detail": f"Tick data file not found: {path}",
            "path": path,
        }

    first_line = ""
    last_line = ""
    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.readline()
        first_line = handle.readline().strip()

    with file_path.open("rb") as handle:
        tail_size = min(file_path.stat().st_size, 8192)
        handle.seek(-tail_size, 2)
        chunk = handle.read().decode("utf-8", errors="ignore")
    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    if lines:
        last_line = lines[-1]

    symbol = file_path.stem.split("_")[0] if "_" in file_path.stem else file_path.stem
    first_tick = _extract_tick_stamp(first_line)
    last_tick = _extract_tick_stamp(last_line)
    size_gb = round(file_path.stat().st_size / (1024 ** 3), 2)

    detail_parts = [
        f"{symbol} tick data ready",
        f"{size_gb} GB",
    ]
    if first_tick and last_tick:
        detail_parts.append(f"{first_tick} -> {last_tick}")

    return {
        "status": "ready",
        "detail": " | ".join(detail_parts),
        "path": str(file_path),
        "symbol": symbol,
        "first_tick": first_tick,
        "last_tick": last_tick,
        "size_gb": size_gb,
    }


def _extract_tick_stamp(line: str) -> str | None:
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    return f"{parts[0]} {parts[1]}"
