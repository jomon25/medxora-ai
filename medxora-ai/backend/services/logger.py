"""
services/logger.py
Lightweight in-memory + file logger for MedXora AI.

Usage
-----
  from services.logger import log_info, log_warn, log_error, get_logs

  log_info("mql5_generator",   "Generated EMA_RSI_ABCD1234.mq5")
  log_error("mt5_runner",      "terminal64.exe not found")
  log_warn("report_parser",    "No sharpe ratio found in report")

  entries = get_logs(limit=50)   # newest first
"""

import logging
import os
from collections import deque
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_DIR

# ── File handler ──────────────────────────────────────────────────────────────

_LOG_FILE = os.path.join(BASE_DIR, "medxora.log")

logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    encoding="utf-8",
)
_file_logger = logging.getLogger("medxora")

# ── In-memory ring buffer (newest first) ──────────────────────────────────────

_BUFFER: deque = deque(maxlen=500)


# ── Public helpers ────────────────────────────────────────────────────────────

def _record(level: str, source: str, message: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level":     level.upper(),
        "source":    source,
        "message":   message,
    }
    _BUFFER.appendleft(entry)

    log_line = f"[{source}] {message}"
    if level == "INFO":
        _file_logger.info(log_line)
    elif level == "WARN":
        _file_logger.warning(log_line)
    elif level == "ERROR":
        _file_logger.error(log_line)


def log_info(source: str, message: str) -> None:
    _record("INFO", source, message)


def log_warn(source: str, message: str) -> None:
    _record("WARN", source, message)


def log_error(source: str, message: str) -> None:
    _record("ERROR", source, message)


def log_event(level: str, message: str, source: str = "pipeline") -> None:
    """
    Compatibility helper for pipeline modules that log with a single function.
    """
    normalized = (level or "INFO").upper()
    if normalized == "ERROR":
        log_error(source, message)
    elif normalized in {"WARN", "WARNING"}:
        log_warn(source, message)
    else:
        log_info(source, message)


def _parse_log_file_line(line: str) -> dict | None:
    parts = [part.strip() for part in line.strip().split(" | ", 2)]
    if len(parts) != 3:
        return None

    timestamp, level, message = parts
    source = "system"

    if message.startswith("[") and "] " in message:
        source_part, message = message.split("] ", 1)
        source = source_part[1:]

    return {
        "timestamp": timestamp,
        "level": level.upper(),
        "source": source,
        "message": message,
    }


def _read_file_logs(limit: int = 100, level_filter: str | None = None) -> list[dict]:
    if not os.path.exists(_LOG_FILE):
        return []

    recent_lines: deque[str] = deque(maxlen=max(limit * 3, limit))

    with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                recent_lines.append(line)

    parsed_logs: list[dict] = []
    for line in reversed(recent_lines):
        entry = _parse_log_file_line(line)
        if not entry:
            continue
        if level_filter and entry["level"] != level_filter.upper():
            continue
        parsed_logs.append(entry)
        if len(parsed_logs) >= limit:
            break

    return parsed_logs


def get_logs(limit: int = 100, level_filter: str | None = None) -> list[dict]:
    """
    Return the most recent log entries (newest first).

    Parameters
    ----------
    limit        : max number of entries to return
    level_filter : "INFO", "WARN", or "ERROR" — None returns all levels
    """
    normalized_level = level_filter.upper() if level_filter else None

    in_memory_entries = list(_BUFFER)
    if normalized_level:
        in_memory_entries = [e for e in in_memory_entries if e["level"] == normalized_level]

    file_entries = _read_file_logs(limit=limit, level_filter=normalized_level)

    merged: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    for entry in in_memory_entries + file_entries:
        signature = (
            entry.get("timestamp", ""),
            entry.get("level", ""),
            entry.get("source", ""),
            entry.get("message", ""),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(entry)

    merged.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return merged[:limit]


def clear_logs() -> None:
    """Wipe the in-memory buffer (file log is unaffected)."""
    _BUFFER.clear()
