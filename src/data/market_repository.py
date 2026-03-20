"""Persistence helpers for fetched market datasets and metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import config
from .market_models import MarketDatasetMetadata

FETCH_SNAPSHOT_PREFIX = "latest_market_data"


def _safe_ticker_name(ticker: str) -> str:
    """Convert ticker symbols to filesystem-safe uppercase tokens."""

    return "".join(char if char.isalnum() or char in {"_", ".", "-"} else "_" for char in ticker.upper())


def _artifact_stem(ticker: str, interval: str) -> str:
    """Build deterministic artifact stem from ticker and interval."""

    safe_ticker = _safe_ticker_name(ticker)
    safe_interval = interval.replace("/", "_")
    return f"latest_market_{safe_ticker}_{safe_interval}"


def save_market_dataset(
    df: pd.DataFrame,
    metadata: MarketDatasetMetadata,
    *,
    market_dir: Path | None = None,
    meta_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Save market dataset to Parquet and sidecar metadata to JSON."""

    target_market_dir = market_dir or config.MARKET_DATA_DIR
    target_meta_dir = meta_dir or config.METADATA_DIR
    target_market_dir.mkdir(parents=True, exist_ok=True)
    target_meta_dir.mkdir(parents=True, exist_ok=True)

    stem = _artifact_stem(metadata.ticker, metadata.interval)
    parquet_path = target_market_dir / f"{stem}.parquet"
    meta_path = target_meta_dir / f"{stem}.json"

    df.to_parquet(parquet_path, index=False)
    meta_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")

    return parquet_path, meta_path


def clear_saved_fetch_snapshots(
    *,
    output_dir: Path | None = None,
    prefix: str = FETCH_SNAPSHOT_PREFIX,
) -> None:
    """Remove prior CSV fetch snapshots before a new save run."""

    target_dir = output_dir or config.DOWNLOADS_DIR
    if not target_dir.exists():
        return

    for existing in target_dir.glob(f"{prefix}_*.csv"):
        if existing.is_file():
            existing.unlink()


def save_market_snapshot_csv(
    df: pd.DataFrame,
    *,
    ticker: str,
    output_dir: Path | None = None,
    prefix: str = FETCH_SNAPSHOT_PREFIX,
) -> Path:
    """Persist fetched market data as a user-facing CSV snapshot."""

    target_dir = output_dir or config.DOWNLOADS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = _safe_ticker_name(ticker)
    output_path = target_dir / f"{prefix}_{safe_ticker}.csv"
    df.to_csv(output_path, index=False)
    return output_path
