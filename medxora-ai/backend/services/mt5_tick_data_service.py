import pandas as pd
import numpy as np


def load_mt5_tick_csv_sample(file_path: str, max_rows: int = 500000):
    """
    Loads MT5 tick export format:
    <DATE> <TIME> <BID> <ASK> <LAST> <VOLUME> <FLAGS>

    Example:
    2020.01.02    06:00:00.286    1.12132    1.12137        6
    """

    df = pd.read_csv(
        file_path,
        sep="\t",
        nrows=max_rows,
        dtype=str,
        engine="python"
    )

    df.columns = [c.strip().replace("<", "").replace(">", "").lower() for c in df.columns]

    required = ["date", "time", "bid", "ask"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}. Found columns: {list(df.columns)}")

    df["timestamp"] = pd.to_datetime(
        df["date"].str.strip() + " " + df["time"].str.strip(),
        format="%Y.%m.%d %H:%M:%S.%f",
        errors="coerce"
    )

    df["bid"] = pd.to_numeric(df["bid"], errors="coerce")
    df["ask"] = pd.to_numeric(df["ask"], errors="coerce")

    # MT5 tick rows sometimes update only bid or ask. Forward fill missing side.
    df["bid"] = df["bid"].ffill()
    df["ask"] = df["ask"].ffill()

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    else:
        df["volume"] = 0

    df = df.dropna(subset=["timestamp", "bid", "ask"])
    df = df[df["ask"] >= df["bid"]]

    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["spread_pips"] = (df["ask"] - df["bid"]) * 10000

    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")

    return df


def ticks_to_ohlcv(ticks: pd.DataFrame, timeframe: str = "5min"):
    bars = pd.DataFrame()

    bars["open"] = ticks["mid"].resample(timeframe).first()
    bars["high"] = ticks["mid"].resample(timeframe).max()
    bars["low"] = ticks["mid"].resample(timeframe).min()
    bars["close"] = ticks["mid"].resample(timeframe).last()
    bars["volume"] = ticks["volume"].resample(timeframe).sum()
    bars["avg_spread_pips"] = ticks["spread_pips"].resample(timeframe).mean()
    bars["tick_count"] = ticks["mid"].resample(timeframe).count()

    bars = bars.dropna()
    bars = bars[bars["tick_count"] > 0]

    bars = bars.reset_index()
    bars["timestamp"] = bars["timestamp"].astype(str)

    return bars


def add_indicators(bars: pd.DataFrame):
    df = bars.copy()

    df["ema_fast"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df.dropna().reset_index(drop=True)
