"""
Data loading utilities.

This module contains the public API for loading strategy reports and market data.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from .market_fetcher import SUPPORTED_INTERVALS, SUPPORTED_PERIODS, fetch_market_data
from .market_models import MarketDatasetMetadata, MarketFetchRequest
from .market_repository import save_market_dataset

# Simple cache for loaded data – in a real project you might use a more robust solution.
_loaded_strategy: pd.DataFrame | None = None
_loaded_market: pd.DataFrame | None = None

__all__ = ["strategy", "market"]

# Strategy sub‑module
class _StrategyModule:
    """
    Provides methods for loading and accessing strategy report data from CSV files.
    """

    def load_csv(self, path: Path) -> pd.DataFrame:
        """
        Load a strategy report from a CSV file.

        Args:
            path (Path): Path to the strategy CSV file.

        Returns:
            pd.DataFrame: Loaded strategy data with normalized columns.
        """

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
        """
        Get the currently loaded strategy DataFrame.

        Returns:
            pd.DataFrame: The loaded strategy data.

        Raises:
            RuntimeError: If no strategy has been loaded yet.
        """

        if _loaded_strategy is None:
            raise RuntimeError("No strategy has been loaded yet")
        return _loaded_strategy

strategy = _StrategyModule()

# Market sub‑module
class _MarketModule:
    """
    Market-data access wrappers.

    Notes:
        Supported period/interval values mirror yfinance's documented
        ``download`` interface.
    """

    SUPPORTED_PERIODS = SUPPORTED_PERIODS
    SUPPORTED_INTERVALS = SUPPORTED_INTERVALS

    def fetch_yfinance(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
        *,
        period: str | None = None,
        interval: str = "1d",
        auto_adjust: bool = False,
        prepost: bool = False,
        actions: bool = False,
    ) -> pd.DataFrame:
        """
        Download market data from yfinance with either date-range or period window.

        Args:
            ticker: Symbol to download, e.g. ``AAPL``.
            start: Inclusive start date in ``YYYY-MM-DD`` format.
            end: Exclusive end date in ``YYYY-MM-DD`` format.
            period: Relative lookback window such as ``1mo`` or ``ytd``.
            interval: Bar interval such as ``1m``, ``5m``, ``30m`` or ``1d``.
            auto_adjust: If true, OHLC prices are adjusted for splits/dividends.
            prepost: If true, include pre/post market data when available.
            actions: If true, include dividends and stock splits columns.

        Returns:
            A normalized DataFrame with lowercase column names and ``date``.
        """

        request = MarketFetchRequest(
            ticker=ticker,
            start=start,
            end=end,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            prepost=prepost,
            actions=actions,
        )
        df = fetch_market_data(request)
        metadata = MarketDatasetMetadata.from_request(request, row_count=len(df))
        save_market_dataset(df=df, metadata=metadata)

        global _loaded_market
        _loaded_market = df
        return df

    def get_loaded(self) -> pd.DataFrame:
        if _loaded_market is None:
            raise RuntimeError("No market data has been fetched yet")
        return _loaded_market

market = _MarketModule()
