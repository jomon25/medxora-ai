from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import MT5_TICK_DATA_PATH, PARQUET_DATA_DIR


RAW_PATH = Path(MT5_TICK_DATA_PATH)
PARQUET_PATH = Path(PARQUET_DATA_DIR) / "EURUSD_ticks.parquet"
METADATA_PATH = Path(PARQUET_DATA_DIR) / "EURUSD_ticks.metadata.json"


def convert_mt5_ticks_to_parquet(
    csv_path: str | Path = RAW_PATH,
    output_path: str | Path = PARQUET_PATH,
    chunk_size: int = 500_000,
) -> dict:
    """
    Convert a MetaTrader 5 tick export into a compact Parquet dataset.

    Expected tab-separated columns:
    <DATE> <TIME> <BID> <ASK> <LAST> <VOLUME> <FLAGS>
    """
    csv_path = Path(csv_path)
    output_path = Path(output_path)
    metadata_path = output_path.with_suffix(".metadata.json")

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {csv_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    total_rows = 0
    bad_rows = 0
    min_date = None
    max_date = None
    symbol = _infer_symbol(csv_path)
    parquet_writer: pq.ParquetWriter | None = None

    try:
        reader = pd.read_csv(
            csv_path,
            sep="\t",
            quotechar='"',
            chunksize=chunk_size,
            low_memory=False,
        )

        for chunk_number, chunk in enumerate(reader, start=1):
            original_len = len(chunk)
            chunk.columns = [
                str(col).replace("<", "").replace(">", "").strip().upper()
                for col in chunk.columns
            ]

            required_columns = {"DATE", "TIME", "BID", "ASK"}
            if not required_columns.issubset(set(chunk.columns)):
                raise ValueError(
                    f"Missing required columns. Found columns: {chunk.columns.tolist()}"
                )

            chunk["timestamp"] = _parse_mt5_timestamps(chunk["DATE"], chunk["TIME"])

            chunk = chunk.rename(
                columns={
                    "BID": "bid",
                    "ASK": "ask",
                    "LAST": "last",
                    "VOLUME": "volume",
                    "FLAGS": "flags",
                }
            )

            if "last" not in chunk.columns:
                chunk["last"] = None
            if "volume" not in chunk.columns:
                chunk["volume"] = 0
            if "flags" not in chunk.columns:
                chunk["flags"] = 0

            for col in ["bid", "ask", "last", "volume", "flags"]:
                chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

            chunk = chunk.dropna(subset=["timestamp", "bid", "ask"])
            chunk = chunk[(chunk["bid"] > 0) & (chunk["ask"] > 0)]
            chunk["mid"] = (chunk["bid"] + chunk["ask"]) / 2
            chunk["spread"] = (chunk["ask"] - chunk["bid"]) * 10000
            chunk = chunk[chunk["spread"] >= 0]
            chunk = chunk[
                [
                    "timestamp",
                    "bid",
                    "ask",
                    "last",
                    "volume",
                    "flags",
                    "mid",
                    "spread",
                ]
            ].sort_values("timestamp")

            clean_len = len(chunk)
            bad_rows += original_len - clean_len
            total_rows += clean_len

            if clean_len == 0:
                continue

            chunk_min = chunk["timestamp"].min()
            chunk_max = chunk["timestamp"].max()
            min_date = chunk_min if min_date is None or chunk_min < min_date else min_date
            max_date = chunk_max if max_date is None or chunk_max > max_date else max_date

            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(output_path, table.schema)

            parquet_writer.write_table(table)
            print(
                f"Chunk {chunk_number} completed | "
                f"Clean rows: {clean_len:,} | Total rows: {total_rows:,}"
            )
    finally:
        if parquet_writer is not None:
            parquet_writer.close()

    metadata = {
        "symbol": symbol,
        "rows": total_rows,
        "bad_rows": bad_rows,
        "start_date": str(min_date) if min_date is not None else None,
        "end_date": str(max_date) if max_date is not None else None,
        "raw_file": str(csv_path),
        "parquet_file": str(output_path),
        "metadata_file": str(metadata_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def get_conversion_metadata(output_path: str | Path = PARQUET_PATH) -> dict | None:
    output_path = Path(output_path)
    metadata_path = output_path.with_suffix(".metadata.json")
    if metadata_path.exists():
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    if not output_path.exists():
        return None
    return {
        "symbol": _infer_symbol(output_path),
        "rows": None,
        "bad_rows": None,
        "start_date": None,
        "end_date": None,
        "raw_file": str(RAW_PATH),
        "parquet_file": str(output_path),
        "metadata_file": str(metadata_path),
    }


def _parse_mt5_timestamps(date_series: pd.Series, time_series: pd.Series) -> pd.Series:
    stamps = date_series.astype(str).str.strip() + " " + time_series.astype(str).str.strip()
    parsed = pd.to_datetime(
        stamps,
        format="%Y.%m.%d %H:%M:%S.%f",
        errors="coerce",
    )
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            stamps.loc[missing],
            format="%Y.%m.%d %H:%M:%S",
            errors="coerce",
        )
    return parsed


def _infer_symbol(path: str | Path) -> str:
    stem = Path(path).stem
    if "_" in stem:
        return stem.split("_")[0].upper()
    return "EURUSD"


if __name__ == "__main__":
    result = convert_mt5_ticks_to_parquet()
    print(json.dumps(result, indent=2))
