import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _resolve_default_tick_data_path() -> str:
    outer_data_dir = os.path.join(os.path.dirname(BASE_DIR), "DATA")
    if not os.path.isdir(outer_data_dir):
        return os.path.join(outer_data_dir, "EURUSD_ticks.csv")

    preferred = []
    fallback = []
    for name in os.listdir(outer_data_dir):
        lower_name = name.lower()
        full_path = os.path.join(outer_data_dir, name)
        if not os.path.isfile(full_path):
            continue
        if lower_name.endswith(".csv"):
            fallback.append(full_path)
            if "tick" in lower_name:
                preferred.append(full_path)

    candidates = preferred or fallback
    if not candidates:
        return os.path.join(outer_data_dir, "EURUSD_ticks.csv")

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]

MT5_PATH = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
# Optional: explicit path to the MT5 terminal data folder (the one that contains MQL5/Experts/).
# If not set, the code will try to detect it automatically.
MT5_DATA_DIR = os.getenv("MT5_DATA_DIR", "")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'medxora.db')}")
CORS_ALLOWED_ORIGINS = _parse_csv_env(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://gen-lang-client-0419797096.web.app",
        "https://gen-lang-client-0419797096.firebaseapp.com",
    ],
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MONGODB_URI = os.getenv("MONGODB_URI", "")
MT5_TICK_DATA_PATH = os.getenv("MT5_TICK_DATA_PATH") or _resolve_default_tick_data_path()

GENERATED_STRATEGIES_DIR = os.path.join(BASE_DIR, "generated_strategies")
BACKTEST_REPORTS_DIR = os.path.join(BASE_DIR, "backtest_reports")
MT5_WORKSPACE_DIR = os.path.join(BASE_DIR, "mt5_workspace")
BACKEND_DATA_DIR = os.path.join(BACKEND_DIR, "data")
PARQUET_DATA_DIR = os.path.join(BACKEND_DATA_DIR, "parquet")
OHLCV_DATA_DIR = os.path.join(BACKEND_DATA_DIR, "ohlcv")
BACKTEST_RESULTS_DIR = os.path.join(BACKEND_DATA_DIR, "backtest_results")

for d in [
    GENERATED_STRATEGIES_DIR,
    BACKTEST_REPORTS_DIR,
    MT5_WORKSPACE_DIR,
    BACKEND_DATA_DIR,
    PARQUET_DATA_DIR,
    OHLCV_DATA_DIR,
    BACKTEST_RESULTS_DIR,
]:
    os.makedirs(d, exist_ok=True)
