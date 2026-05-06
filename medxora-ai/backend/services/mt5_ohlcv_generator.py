from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from config import OHLCV_DATA_DIR, PARQUET_DATA_DIR


TICK_PARQUET_PATH = Path(PARQUET_DATA_DIR) / "EURUSD_ticks.parquet"
OUTPUT_DIR = Path(OHLCV_DATA_DIR)
SUMMARY_PATH = OUTPUT_DIR / "EURUSD_summary.json"
TIMEFRAMES = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}


def generate_ohlcv_from_mt5_ticks(
    input_path: str | Path = TICK_PARQUET_PATH,
    symbol: str = "EURUSD",
    batch_size: int = 500_000,
) -> list[dict]:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {input_path}. Run mt5_tick_converter.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    partials: dict[str, list[pd.DataFrame]] = {label: [] for label in TIMEFRAMES}
    parquet_file = pq.ParquetFile(input_path)

    for batch_number, batch in enumerate(
        parquet_file.iter_batches(
            batch_size=batch_size,
            columns=["timestamp", "mid", "volume", "spread"],
        ),
        start=1,
    ):
        df = batch.to_pandas()
        if df.empty:
            continue

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").set_index("timestamp")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["spread"] = pd.to_numeric(df["spread"], errors="coerce").fillna(0)

        for label, rule in TIMEFRAMES.items():
            partial = _resample_batch(df, rule)
            if not partial.empty:
                partials[label].append(partial)

        print(f"Processed parquet batch {batch_number}")

    generated_files = []
    summary = {
        "symbol": symbol,
        "source": str(input_path),
        "files": [],
    }

    for label in TIMEFRAMES:
        output_path = OUTPUT_DIR / f"{symbol}_{label}.parquet"
        combined = _merge_partials(partials[label])
        if combined.empty:
            continue

        combined.to_parquet(output_path, index=True)
        info = {
            "symbol": symbol,
            "timeframe": label,
            "rows": int(len(combined)),
            "file": str(output_path),
            "start_date": str(combined.index.min()),
            "end_date": str(combined.index.max()),
            "avg_spread": round(float(combined["avg_spread"].mean()), 5),
        }
        generated_files.append(info)
        summary["files"].append(info)

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return generated_files


def get_ohlcv_summary(symbol: str = "EURUSD") -> dict:
    if SUMMARY_PATH.exists():
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    files = []
    for label in TIMEFRAMES:
        path = OUTPUT_DIR / f"{symbol}_{label}.parquet"
        files.append(
            {
                "symbol": symbol,
                "timeframe": label,
                "file": str(path),
                "status": "ready" if path.exists() else "missing",
            }
        )
    return {
        "symbol": symbol,
        "source": str(TICK_PARQUET_PATH),
        "files": files,
    }


def _resample_batch(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    partial = pd.DataFrame()
    partial["open"] = df["mid"].resample(rule).first()
    partial["high"] = df["mid"].resample(rule).max()
    partial["low"] = df["mid"].resample(rule).min()
    partial["close"] = df["mid"].resample(rule).last()
    partial["volume"] = df["volume"].resample(rule).sum()
    partial["tick_count"] = df["mid"].resample(rule).count()
    partial["spread_sum"] = df["spread"].resample(rule).sum()
    partial["max_spread"] = df["spread"].resample(rule).max()
    partial["min_spread"] = df["spread"].resample(rule).min()
    partial = partial.dropna(subset=["open", "high", "low", "close"])
    partial = partial[partial["tick_count"] > 0]
    partial.index.name = "timestamp"
    return partial.reset_index()


def _merge_partials(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    if not chunks:
        return pd.DataFrame()

    combined = pd.concat(chunks, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"])
    combined = combined.sort_values("timestamp")
    merged = combined.groupby("timestamp", sort=True, as_index=True).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "tick_count": "sum",
            "spread_sum": "sum",
            "max_spread": "max",
            "min_spread": "min",
        }
    )
    merged["avg_spread"] = merged["spread_sum"] / merged["tick_count"].replace(0, pd.NA)
    merged = merged.drop(columns=["spread_sum"])
    return merged[
        [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "tick_count",
            "avg_spread",
            "max_spread",
            "min_spread",
        ]
    ]


if __name__ == "__main__":
    result = generate_ohlcv_from_mt5_ticks()
    print(json.dumps(result, indent=2))
