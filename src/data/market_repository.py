"""Persistence helpers for fetched market datasets and metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import config
from .market_models import MarketDatasetMetadata


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
