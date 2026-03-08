"""yfinance integration and market-data normalization logic."""

from __future__ import annotations

import pandas as pd

from .market_models import MarketFetchRequest

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


def _validate_fetch_window(request: MarketFetchRequest) -> None:
    """Validate start/end/period combinations before requesting data."""

    if request.period is not None and (request.start is not None or request.end is not None):
        raise ValueError("--period cannot be combined with --start/--end")
    if request.end is not None and request.start is None:
        raise ValueError("--end requires --start")
    if request.start is not None and request.end is not None:
        start_dt = pd.to_datetime(request.start)
        end_dt = pd.to_datetime(request.end)
        if start_dt > end_dt:
            raise ValueError("--start must be before or equal to --end")


def _normalize_downloaded_frame(downloaded: pd.DataFrame) -> pd.DataFrame:
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


def fetch_market_data(request: MarketFetchRequest) -> pd.DataFrame:
    """Fetch and normalize market data from yfinance."""

    if not request.ticker or not request.ticker.strip():
        raise ValueError("ticker must be a non-empty string")
    if request.interval not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval '{request.interval}'. Supported values: {', '.join(SUPPORTED_INTERVALS)}"
        )
    if request.period is not None and request.period not in SUPPORTED_PERIODS:
        raise ValueError(
            f"Unsupported period '{request.period}'. Supported values: {', '.join(SUPPORTED_PERIODS)}"
        )

    _validate_fetch_window(request)

    import yfinance as yf

    downloaded = yf.download(
        tickers=request.ticker,
        start=request.start,
        end=request.end,
        period=request.period,
        interval=request.interval,
        auto_adjust=request.auto_adjust,
        prepost=request.prepost,
        actions=request.actions,
        progress=False,
    )
    if not isinstance(downloaded, pd.DataFrame):
        raise RuntimeError("Failed to download market data")

    return _normalize_downloaded_frame(downloaded)
