"""Read-side access helpers for persisted market datasets and metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import config
from .market_models import MarketDatasetMetadata
from .market_repository import _artifact_stem


class MarketDataAccess:
    """Provide typed read access to persisted market artifacts."""

    def __init__(
        self,
        *,
        market_dir: Path | None = None,
        meta_dir: Path | None = None,
    ) -> None:
        self._market_dir = market_dir or config.MARKET_DATA_DIR
        self._meta_dir = meta_dir or config.METADATA_DIR

    def dataset_paths(self, ticker: str, interval: str) -> tuple[Path, Path]:
        """Return expected parquet and metadata paths for a ticker/interval pair."""

        stem = _artifact_stem(ticker, interval)
        parquet_path = self._market_dir / f"{stem}.parquet"
        meta_path = self._meta_dir / f"{stem}.json"
        return parquet_path, meta_path

    def has_dataset(self, ticker: str, interval: str) -> bool:
        """Return true only when both parquet and metadata artifacts exist."""

        parquet_path, meta_path = self.dataset_paths(ticker, interval)
        return parquet_path.exists() and meta_path.exists()

    def load_dataset(self, ticker: str, interval: str) -> pd.DataFrame:
        """Load persisted parquet dataset for a ticker/interval pair."""

        parquet_path, _meta_path = self.dataset_paths(ticker, interval)
        if not parquet_path.exists():
            raise FileNotFoundError(
                f"Market dataset not found for ticker={ticker} interval={interval}. "
                f"Expected file: {parquet_path}"
            )
        return pd.read_parquet(parquet_path)

    def load_metadata(self, ticker: str, interval: str) -> MarketDatasetMetadata:
        """Load typed metadata for a ticker/interval pair."""

        _parquet_path, meta_path = self.dataset_paths(ticker, interval)
        if not meta_path.exists():
            raise FileNotFoundError(
                f"Market metadata not found for ticker={ticker} interval={interval}. "
                f"Expected file: {meta_path}"
            )

        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid metadata format in {meta_path}")
        return MarketDatasetMetadata.from_dict(payload)


market_data_access = MarketDataAccess()
