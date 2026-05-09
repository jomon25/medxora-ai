import pandas as pd
from datetime import datetime
from uuid import uuid4

from services.mt5_tick_data_service import load_mt5_tick_csv_sample, ticks_to_ohlcv, add_indicators
from database.mongodb import backtests_collection


def run_mt5_ema_rsi_backtest(
    file_path: str,
    timeframe: str = "5min",
    max_rows: int = 100000,
    spread_limit_pips: float = 2.0,
    risk_reward: float = 1.5,
):
    ticks = load_mt5_tick_csv_sample(file_path, max_rows=max_rows)
    bars = ticks_to_ohlcv(ticks, timeframe=timeframe)
    df = add_indicators(bars)

    trades = []
    position = None

    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if row["avg_spread_pips"] > spread_limit_pips:
            continue

        ts = pd.to_datetime(row["timestamp"])

        # London session
        if not (7 <= ts.hour <= 16):
            continue

        buy_signal = row["ema_fast"] > row["ema_slow"] and row["rsi"] < 45
        sell_signal = row["ema_fast"] < row["ema_slow"] and row["rsi"] > 55

        entry_price = next_row["open"]

        if position is None and buy_signal:
            sl = entry_price - row["atr"] * 1.5
            tp = entry_price + (entry_price - sl) * risk_reward
            position = {
                "side": "buy",
                "entry_time": next_row["timestamp"],
                "entry_price": entry_price,
                "sl": sl,
                "tp": tp,
            }

        elif position is None and sell_signal:
            sl = entry_price + row["atr"] * 1.5
            tp = entry_price - (sl - entry_price) * risk_reward
            position = {
                "side": "sell",
                "entry_time": next_row["timestamp"],
                "entry_price": entry_price,
                "sl": sl,
                "tp": tp,
            }

        elif position is not None:
            high = row["high"]
            low = row["low"]
            exit_price = None
            exit_reason = None

            if position["side"] == "buy":
                if low <= position["sl"]:
                    exit_price = position["sl"]
                    exit_reason = "stop_loss"
                elif high >= position["tp"]:
                    exit_price = position["tp"]
                    exit_reason = "take_profit"

                if exit_price:
                    pnl_pips = (exit_price - position["entry_price"]) * 10000

            else:
                if high >= position["sl"]:
                    exit_price = position["sl"]
                    exit_reason = "stop_loss"
                elif low <= position["tp"]:
                    exit_price = position["tp"]
                    exit_reason = "take_profit"

                if exit_price:
                    pnl_pips = (position["entry_price"] - exit_price) * 10000

            if exit_price:
                trades.append({
                    "side": position["side"],
                    "entry_time": position["entry_time"],
                    "exit_time": row["timestamp"],
                    "entry_price": float(position["entry_price"]),
                    "exit_price": float(exit_price),
                    "pnl_pips": float(pnl_pips),
                    "exit_reason": exit_reason,
                })
                position = None

    if not trades:
        metrics = {
            "total_trades": 0,
            "net_pips": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "max_drawdown_pips": 0,
        }
    else:
        trade_df = pd.DataFrame(trades)
        wins = trade_df[trade_df["pnl_pips"] > 0]
        losses = trade_df[trade_df["pnl_pips"] < 0]

        gross_profit = wins["pnl_pips"].sum() if len(wins) else 0
        gross_loss = abs(losses["pnl_pips"].sum()) if len(losses) else 0

        equity = trade_df["pnl_pips"].cumsum()
        peak = equity.cummax()
        drawdown = equity - peak

        metrics = {
            "total_trades": int(len(trade_df)),
            "net_pips": float(trade_df["pnl_pips"].sum()),
            "win_rate": float((len(wins) / len(trade_df)) * 100),
            "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else 0,
            "max_drawdown_pips": float(drawdown.min()),
        }

    return {
        "backtest_id": f"bt_{uuid4().hex[:12]}",
        "strategy_name": "MT5 EURUSD EMA RSI London Scalper",
        "dataset_format": "MT5 tick export",
        "file_path": file_path,
        "timeframe": timeframe,
        "max_rows": max_rows,
        "metrics": metrics,
        "trades": trades[:300],
        "created_at": datetime.utcnow().isoformat(),
    }


async def run_and_save_mt5_backtest(
    file_path: str,
    timeframe: str = "5min",
    max_rows: int = 100000,
):
    result = run_mt5_ema_rsi_backtest(
        file_path=file_path,
        timeframe=timeframe,
        max_rows=max_rows,
    )

    await backtests_collection.insert_one(result.copy())
    result.pop("_id", None)

    return result
