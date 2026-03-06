"""
Data loading utilities.

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

    SUPPORTED_PERIODS: tuple[str, ...] = (
        "1d",
        "5d",
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "5y",
        "10y",
        "ytd",
        "max",
    )
    SUPPORTED_INTERVALS: tuple[str, ...] = (
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    )

    def _validate_fetch_window(
        self,
        start: str | None,
        end: str | None,
        period: str | None,
    ) -> None:
        """Validate start/end/period combinations before requesting data."""

        if period is not None and (start is not None or end is not None):
            raise ValueError("--period cannot be combined with --start/--end")
        if end is not None and start is None:
            raise ValueError("--end requires --start")
        if start is not None and end is not None:
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            if start_dt > end_dt:
                raise ValueError("--start must be before or equal to --end")

    def _normalize_downloaded_frame(self, downloaded: pd.DataFrame) -> pd.DataFrame:
        """Normalize yfinance output into a consistent, merge-friendly schema."""

        if isinstance(downloaded.columns, pd.MultiIndex):
            downloaded = downloaded.copy()
            downloaded.columns = downloaded.columns.get_level_values(0)

        df = downloaded.reset_index().rename(
            columns={
                "Date": "date",
                "Datetime": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

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

        if not ticker or not ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                f"Unsupported interval '{interval}'. Supported values: {', '.join(self.SUPPORTED_INTERVALS)}"
            )
        if period is not None and period not in self.SUPPORTED_PERIODS:
            raise ValueError(
                f"Unsupported period '{period}'. Supported values: {', '.join(self.SUPPORTED_PERIODS)}"
            )
        self._validate_fetch_window(start=start, end=end, period=period)

        import yfinance as yf

        downloaded = yf.download(
            tickers=ticker,
            start=start,
            end=end,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            prepost=prepost,
            actions=actions,
            progress=False,
        )
        if not isinstance(downloaded, pd.DataFrame):
            raise RuntimeError("Failed to download market data")

        df = self._normalize_downloaded_frame(downloaded)
        global _loaded_market
        _loaded_market = df
        return df

    def get_loaded(self) -> pd.DataFrame:
        if _loaded_market is None:
            raise RuntimeError("No market data has been fetched yet")
        return _loaded_market

market = _MarketModule()
