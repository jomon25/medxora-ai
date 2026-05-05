import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default
    return [item.strip() for item in raw_value.split(",") if item.strip()]

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
    ],
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MONGODB_URI = os.getenv("MONGODB_URI", "")
MT5_TICK_DATA_PATH = os.getenv(
    "MT5_TICK_DATA_PATH",
    r"C:\Users\jomon\Desktop\MedXora AI\DATA\EURUSD_202001020600_202604291148.csv",
)

GENERATED_STRATEGIES_DIR = os.path.join(BASE_DIR, "generated_strategies")
BACKTEST_REPORTS_DIR = os.path.join(BASE_DIR, "backtest_reports")
MT5_WORKSPACE_DIR = os.path.join(BASE_DIR, "mt5_workspace")

for d in [GENERATED_STRATEGIES_DIR, BACKTEST_REPORTS_DIR, MT5_WORKSPACE_DIR]:
    os.makedirs(d, exist_ok=True)
