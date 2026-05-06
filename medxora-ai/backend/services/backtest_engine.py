from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import BACKTEST_RESULTS_DIR, OHLCV_DATA_DIR


RESULT_PATH = Path(BACKTEST_RESULTS_DIR) / "eurusd_demo_backtest.json"
ANNUALIZATION_FACTORS = {
    "M1": 365 * 24 * 60,
    "M5": 365 * 24 * 12,
    "M15": 365 * 24 * 4,
    "M30": 365 * 24 * 2,
    "H1": 365 * 24,
    "H4": 365 * 6,
    "D1": 365,
}


def calculate_max_drawdown(equity_series: pd.Series) -> float:
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak.replace(0, pd.NA)
    return float(drawdown.min() * 100)


def calculate_sharpe_ratio(returns: pd.Series, timeframe: str) -> float:
    clean_returns = returns.replace([pd.NA], 0).dropna()
    if clean_returns.empty or clean_returns.std(ddof=0) == 0:
        return 0.0
    annual_factor = ANNUALIZATION_FACTORS.get(timeframe, ANNUALIZATION_FACTORS["M15"])
    return float((clean_returns.mean() / clean_returns.std(ddof=0)) * (annual_factor ** 0.5))


def summarize_trades(strategy_returns: pd.Series, positions: pd.Series, initial_balance: float) -> dict:
    active = pd.DataFrame({
        "position": positions,
        "strategy_returns": strategy_returns,
    })
    active = active[active["position"] != 0].copy()
    if active.empty:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "expected_payoff": 0.0,
            "trade_pnls": [],
        }

    active["segment"] = (active["position"] != active["position"].shift()).cumsum()
    trade_returns = active.groupby("segment")["strategy_returns"].apply(lambda series: (1 + series).prod() - 1)
    trade_pnls = (trade_returns * initial_balance).tolist()
    gross_profit = float(sum(value for value in trade_pnls if value > 0))
    gross_loss = float(sum(value for value in trade_pnls if value < 0))
    trade_count = len(trade_pnls)
    win_count = sum(1 for value in trade_pnls if value > 0)
    return {
        "trade_count": trade_count,
        "win_rate": (win_count / trade_count) * 100 if trade_count else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss < 0 else (gross_profit if gross_profit > 0 else 0.0),
        "expected_payoff": sum(trade_pnls) / trade_count if trade_count else 0.0,
        "trade_pnls": trade_pnls,
    }


def run_ema_backtest(
    symbol: str = "EURUSD",
    timeframe: str = "M5",
    fast_ema: int = 20,
    slow_ema: int = 50,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_balance: float = 10000.0,
) -> dict:
    path = Path(OHLCV_DATA_DIR) / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"OHLCV file not found: {path}. Generate OHLCV first.")

    df = pd.read_parquet(path).reset_index()
    if "timestamp" not in df.columns:
        df = df.rename(columns={df.columns[0]: "timestamp"})

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    if start_date:
        df = df[df["timestamp"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["timestamp"] <= pd.to_datetime(end_date)]

    if len(df) < slow_ema + 10:
        raise ValueError("Not enough bars for this backtest date range.")

    df["fast_ema"] = df["close"].ewm(span=fast_ema, adjust=False).mean()
    df["slow_ema"] = df["close"].ewm(span=slow_ema, adjust=False).mean()
    df["signal"] = 0
    df.loc[df["fast_ema"] > df["slow_ema"], "signal"] = 1
    df.loc[df["fast_ema"] < df["slow_ema"], "signal"] = -1

    # Prevent look-ahead bias by applying the bar's decision on the next bar.
    df["position"] = df["signal"].shift(1).fillna(0)
    df["returns"] = df["close"].pct_change().fillna(0)
    df["position_change"] = df["position"].diff().abs().fillna(0)

    spread_decimal = (df["avg_spread"].fillna(0) / 10000) / df["close"].replace(0, pd.NA)
    trade_cost = (df["position_change"] * spread_decimal.fillna(0)) / 2
    df["strategy_returns"] = (df["position"] * df["returns"]) - trade_cost
    df["equity"] = (1 + df["strategy_returns"]).cumprod() * initial_balance

    trade_summary = summarize_trades(df["strategy_returns"], df["position"], initial_balance)
    net_return_pct = ((df["equity"].iloc[-1] / initial_balance) - 1) * 100
    net_profit = float(df["equity"].iloc[-1] - initial_balance)
    max_drawdown_pct = calculate_max_drawdown(df["equity"])
    trade_count = int(trade_summary["trade_count"])
    sharpe_ratio = calculate_sharpe_ratio(df["strategy_returns"], timeframe)
    recovery_factor = net_profit / abs(max_drawdown_pct) if max_drawdown_pct not in (0, None) else 0.0
    bars_per_month = {
        "M1": 30 * 24 * 60,
        "M5": 30 * 24 * 12,
        "M15": 30 * 24 * 4,
        "M30": 30 * 24 * 2,
        "H1": 30 * 24,
        "H4": 30 * 6,
        "D1": 30,
    }.get(timeframe, 30 * 24 * 4)
    bars_per_year = {
        "M1": 365 * 24 * 60,
        "M5": 365 * 24 * 12,
        "M15": 365 * 24 * 4,
        "M30": 365 * 24 * 2,
        "H1": 365 * 24,
        "H4": 365 * 6,
        "D1": 365,
    }.get(timeframe, 365 * 24 * 4)
    monthly_profit = net_profit * (bars_per_month / max(len(df), 1))
    yearly_profit = net_profit * (bars_per_year / max(len(df), 1))

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": "EMA Crossover",
        "fast_ema": fast_ema,
        "slow_ema": slow_ema,
        "start_date": str(df["timestamp"].min()),
        "end_date": str(df["timestamp"].max()),
        "bars": int(len(df)),
        "net_return_pct": round(float(net_return_pct), 2),
        "net_profit": round(net_profit, 2),
        "max_drawdown_pct": round(float(max_drawdown_pct), 2),
        "total_trades": trade_count,
        "win_rate": round(float(trade_summary["win_rate"]), 2),
        "gross_profit": round(float(trade_summary["gross_profit"]), 2),
        "gross_loss": round(float(trade_summary["gross_loss"]), 2),
        "profit_factor": round(float(trade_summary["profit_factor"]), 4),
        "expected_payoff": round(float(trade_summary["expected_payoff"]), 4),
        "sharpe_ratio": round(float(sharpe_ratio), 4),
        "recovery_factor": round(float(recovery_factor), 4),
        "monthly_profit": round(float(monthly_profit), 2),
        "yearly_profit": round(float(yearly_profit), 2),
        "initial_balance": initial_balance,
        "final_equity": round(float(df["equity"].iloc[-1]), 2),
        "average_spread_pips": round(float(df["avg_spread"].mean()), 5),
        "data_source": "EURUSD real tick-derived OHLCV",
        "equity_curve": [
            {
                "timestamp": str(row["timestamp"]),
                "equity": round(float(row["equity"]), 2),
            }
            for _, row in df[["timestamp", "equity"]].tail(500).iterrows()
        ],
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp_label = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    report_path = RESULT_PATH.parent / f"{symbol.lower()}_{timeframe.lower()}_{timestamp_label}.json"
    result["report_file"] = str(report_path)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def get_latest_backtest_result() -> dict | None:
    if not RESULT_PATH.exists():
        return None
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = run_ema_backtest(
        symbol="EURUSD",
        timeframe="M5",
        fast_ema=20,
        slow_ema=50,
        start_date="2020-01-02",
        end_date="2020-02-01",
    )
    print(json.dumps(result, indent=2))
