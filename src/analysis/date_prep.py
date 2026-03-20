"""Date and interval preparation helpers for analysis workflows."""

from __future__ import annotations

import pandas as pd

INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
DAILY_INTERVALS = {"1d", "5d"}
LONG_TERM_INTERVALS = {"1wk", "1mo", "3mo"}


def map_interval_to_category(interval: str) -> str:
    """Return strategy category implied by a market-data interval."""

    if interval in INTRADAY_INTERVALS:
        return "intraday"
    if interval in DAILY_INTERVALS:
        return "daily"
    if interval in LONG_TERM_INTERVALS:
        return "long-term"
    raise ValueError(f"No strategy category mapping exists for interval '{interval}'")


def normalize_strategy_market_dates(
    *,
    strategy_df: pd.DataFrame,
    market_df: pd.DataFrame,
    interval: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize strategy/market date keys so merge uses compatible types."""

    if "date" not in strategy_df.columns:
        raise ValueError("Strategy dataframe is missing required 'date' column")
    if "date" not in market_df.columns:
        raise ValueError("Market dataframe is missing required 'date' column")

    strategy = strategy_df.copy()
    market = market_df.copy()
    strategy_dates = pd.to_datetime(strategy["date"], errors="coerce")
    market_dates = pd.to_datetime(market["date"], errors="coerce")

    if strategy_dates.isna().any():
        raise ValueError("Strategy dataframe contains invalid date values")
    if market_dates.isna().any():
        raise ValueError("Market dataframe contains invalid date values")

    if interval in DAILY_INTERVALS or interval in LONG_TERM_INTERVALS:
        strategy["date"] = strategy_dates.dt.strftime("%Y-%m-%d")
        market["date"] = market_dates.dt.strftime("%Y-%m-%d")
    else:
        strategy["date"] = strategy_dates.dt.strftime("%Y-%m-%d %H:%M:%S")
        market["date"] = market_dates.dt.strftime("%Y-%m-%d %H:%M:%S")

    return strategy, market
