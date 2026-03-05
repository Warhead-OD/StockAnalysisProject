"""Data loading utilities.

This module contains the public API for loading strategy reports and market data.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

# Simple cache for loaded data – in a real project you might use a more robust solution.
_loaded_strategy: pd.DataFrame | None = None
_loaded_market: pd.DataFrame | None = None

__all__ = ["strategy", "market"]

# Strategy sub‑module
class _StrategyModule:
    def load_csv(self, path: Path) -> pd.DataFrame:
        global _loaded_strategy
        # The sample CSV uses ';' as separator and has metadata rows before the header.
        df = pd.read_csv(
            path,
            sep=";",
            skiprows=5,
            parse_dates=["Date/Time"],
            date_format="%m/%d/%y %I:%M %p",
        )
        # Normalise column names for tests
        df.rename(columns={"Date/Time": "date", "P/L": "return"}, inplace=True)
        _loaded_strategy = df
        return df

    def get_loaded(self) -> pd.DataFrame:
        if _loaded_strategy is None:
            raise RuntimeError("No strategy has been loaded yet")
        return _loaded_strategy

strategy = _StrategyModule()

# Market sub‑module
class _MarketModule:
    def fetch_yfinance(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        import yfinance as yf

        downloaded = yf.download(ticker, start=start, end=end, progress=False)
        if not isinstance(downloaded, pd.DataFrame):
            raise RuntimeError("Failed to download market data")

        df = downloaded.reset_index().rename(columns={"Adj Close": "adj_close"})
        global _loaded_market
        _loaded_market = df
        return df

    def get_loaded(self) -> pd.DataFrame:
        if _loaded_market is None:
            raise RuntimeError("No market data has been fetched yet")
        return _loaded_market

market = _MarketModule()
