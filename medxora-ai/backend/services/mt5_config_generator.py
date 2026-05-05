import os
import shutil
import subprocess
import time

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MT5_PATH,
    MT5_DATA_DIR,
    MT5_WORKSPACE_DIR,
    BACKTEST_REPORTS_DIR,
    GENERATED_STRATEGIES_DIR,
)

_EA_SUBFOLDER = "GeneratedStrategies"


# ── MT5 data-directory detection ──────────────────────────────────────────────

def _find_mt5_data_dir() -> str | None:
    """
    Return the MT5 terminal data directory (the folder that contains MQL5/Experts/).

    MT5 can run in two modes:
      - Portable: data lives next to terminal64.exe  →  <install_dir>/MQL5/Experts/
      - Normal:   data lives in AppData               →  %APPDATA%/MetaQuotes/Terminal/<hash>/MQL5/Experts/

    The env-var MT5_DATA_DIR (from .env) is checked first.
    """
    # 1. Explicit override from .env
    if MT5_DATA_DIR and os.path.exists(os.path.join(MT5_DATA_DIR, "MQL5", "Experts")):
        return MT5_DATA_DIR

    # 2. Portable mode — data sits next to the executable
    install_dir = os.path.dirname(MT5_PATH)
    if os.path.exists(os.path.join(install_dir, "MQL5", "Experts")):
        return install_dir

    # 3. Normal mode — scan %APPDATA%\MetaQuotes\Terminal\
    appdata = os.environ.get("APPDATA", "")
    terminal_root = os.path.join(appdata, "MetaQuotes", "Terminal")
    if os.path.exists(terminal_root):
        for entry in os.listdir(terminal_root):
            candidate = os.path.join(terminal_root, entry)
            if os.path.exists(os.path.join(candidate, "MQL5", "Experts")):
                return candidate

    return None


# ── Compile step ──────────────────────────────────────────────────────────────

def _copy_and_compile(strategy_name: str, data_dir: str) -> tuple[bool, str]:
    """
    Copy <strategy_name>.mq5 into MT5's Experts/GeneratedStrategies/ folder and
    compile it to .ex5 using MT5's /compile flag.

    Returns (success, message_or_ex5_path).
    """
    src_mq5 = os.path.join(GENERATED_STRATEGIES_DIR, f"{strategy_name}.mq5")
    if not os.path.exists(src_mq5):
        return False, f".mq5 source not found: {src_mq5}"

    experts_sub = os.path.join(data_dir, "MQL5", "Experts", _EA_SUBFOLDER)
    os.makedirs(experts_sub, exist_ok=True)

    dst_mq5 = os.path.join(experts_sub, f"{strategy_name}.mq5")
    shutil.copy2(src_mq5, dst_mq5)

    dst_ex5 = os.path.join(experts_sub, f"{strategy_name}.ex5")

    # Launch MT5 with /compile — it exits after compiling
    try:
        subprocess.run(
            [MT5_PATH, f"/compile:{dst_mq5}", "/log"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        pass  # MT5 may still have finished writing the .ex5

    # Poll briefly because MT5 can be slow to flush the file
    for _ in range(6):
        if os.path.exists(dst_ex5) and os.path.getsize(dst_ex5) > 0:
            return True, dst_ex5
        time.sleep(2)

    return False, f"Compiled .ex5 not produced at: {dst_ex5}"


# ── INI config generator ──────────────────────────────────────────────────────

def generate_config(
    strategy_name: str,
    from_date: str = "2020.01.01",
    to_date: str = "2024.01.01",
    symbol: str = "EURUSD",
    period: str = "M15",
    deposit: int = 10000,
) -> str:
    """Write an MT5 tester .ini and return its path."""
    # Expert= must be relative to MQL5/Experts/ and without the .ex5 extension
    expert_rel = f"{_EA_SUBFOLDER}\\{strategy_name}"
    report_path = os.path.join(BACKTEST_REPORTS_DIR, strategy_name)

    config = (
        "[Tester]\n"
        f"Expert={expert_rel}\n"
        f"Symbol={symbol}\n"
        f"Period={period}\n"
        "Model=0\n"           # Every tick
        f"FromDate={from_date}\n"
        f"ToDate={to_date}\n"
        f"Deposit={deposit}\n"
        "Currency=USD\n"
        "Leverage=100\n"
        "ExecutionMode=0\n"
        "Optimization=0\n"
        "Visual=0\n"
        f"Report={report_path}\n"
        "ReplaceReport=1\n"
        "ShutdownTerminal=1\n"
    )

    config_path = os.path.join(MT5_WORKSPACE_DIR, f"{strategy_name}.ini")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config)

    return config_path


# ── Report polling ────────────────────────────────────────────────────────────

def _wait_for_report(report_base: str, max_wait: int = 60) -> str | None:
    """
    Poll for the report file MT5 produces after a backtest.
    MT5 normally writes <report_base>.htm  (not .html).
    """
    extensions = [".htm", ".html", ".xml"]
    deadline = time.time() + max_wait
    while time.time() < deadline:
        for ext in extensions:
            path = report_base + ext
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        time.sleep(3)
    return None


# ── Main entry point ──────────────────────────────────────────────────────────

def run_backtest(strategy_name: str) -> dict:
    """
    Full pipeline:
      1. Verify MT5 is installed
      2. Find MT5 data directory
      3. Copy .mq5 → MT5 Experts folder and compile → .ex5
      4. Write .ini config
      5. Launch MT5 /config:<ini>  (MT5 runs backtest then closes)
      6. Wait for the report file
      7. Return result dict
    """
    if not os.path.exists(MT5_PATH):
        return {
            "status": "error",
            "message": f"MT5 terminal not found: {MT5_PATH}. "
                       "Set MT5_PATH in .env to the correct terminal64.exe path.",
        }

    data_dir = _find_mt5_data_dir()
    if data_dir is None:
        return {
            "status": "error",
            "message": (
                "Could not locate MT5 data directory (MQL5/Experts/ not found). "
                "Set MT5_DATA_DIR in your .env file to the folder that contains MQL5/."
            ),
        }

    compiled, compile_info = _copy_and_compile(strategy_name, data_dir)
    if not compiled:
        return {
            "status": "error",
            "message": f"EA compilation failed: {compile_info}",
        }

    config_path = generate_config(strategy_name)
    report_base = os.path.join(BACKTEST_REPORTS_DIR, strategy_name)

    try:
        proc = subprocess.run(
            [MT5_PATH, f"/config:{config_path}"],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": "MT5 did not finish within 10 minutes."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    report_file = _wait_for_report(report_base)

    if report_file is None:
        return {
            "status": "error",
            "message": (
                "MT5 exited but the report file was not created. "
                "Check: EA compiled correctly, symbol name matches your broker, "
                "and MT5 has historical data for the requested date range."
            ),
            "config_path": config_path,
            "expected_report_base": report_base,
            "return_code": proc.returncode,
            "mt5_stdout": (proc.stdout or "")[-2000:],
            "mt5_stderr": (proc.stderr or "")[-2000:],
        }

    return {
        "status": "success",
        "message": "Backtest completed successfully.",
        "report_file": report_file,
        "config_path": config_path,
        "return_code": proc.returncode,
    }
