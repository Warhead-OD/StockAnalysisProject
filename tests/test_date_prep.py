"""Unit tests for reusable analysis date-prep helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis import date_prep


def test_map_interval_to_category_returns_expected_labels() -> None:
    """Interval-to-category mapping should match analysis workflow expectations."""

    assert date_prep.map_interval_to_category("15m") == "intraday"
    assert date_prep.map_interval_to_category("1d") == "daily"
    assert date_prep.map_interval_to_category("1wk") == "long-term"


def test_map_interval_to_category_raises_for_unknown_interval() -> None:
    """Unknown intervals should raise a clear value error."""

    with pytest.raises(ValueError, match="No strategy category mapping exists"):
        date_prep.map_interval_to_category("7h")


def test_normalize_strategy_market_dates_daily_uses_date_only_keys() -> None:
    """Daily and longer intervals should normalize to YYYY-MM-DD."""

    strategy_df = pd.DataFrame(
        {
            "date": ["2026-01-01 10:15:00", "2026-01-02 13:45:00"],
            "return": [0.01, -0.02],
        }
    )
    market_df = pd.DataFrame(
        {
            "date": ["2026-01-01 09:30:00", "2026-01-02 16:00:00"],
            "adj_close": [100.0, 99.0],
        }
    )

    normalized_strategy, normalized_market = date_prep.normalize_strategy_market_dates(
        strategy_df=strategy_df,
        market_df=market_df,
        interval="1d",
    )

    assert normalized_strategy["date"].tolist() == ["2026-01-01", "2026-01-02"]
    assert normalized_market["date"].tolist() == ["2026-01-01", "2026-01-02"]


def test_normalize_strategy_market_dates_intraday_uses_timestamp_keys() -> None:
    """Intraday intervals should normalize to second-resolution timestamps."""

    strategy_df = pd.DataFrame(
        {
            "date": ["2026-01-01 10:15:00", "2026-01-01 10:30:00"],
            "return": [0.01, -0.02],
        }
    )
    market_df = pd.DataFrame(
        {
            "date": ["2026-01-01 10:15:00", "2026-01-01 10:30:00"],
            "adj_close": [100.0, 99.0],
        }
    )

    normalized_strategy, normalized_market = date_prep.normalize_strategy_market_dates(
        strategy_df=strategy_df,
        market_df=market_df,
        interval="15m",
    )

    assert normalized_strategy["date"].tolist() == ["2026-01-01 10:15:00", "2026-01-01 10:30:00"]
    assert normalized_market["date"].tolist() == ["2026-01-01 10:15:00", "2026-01-01 10:30:00"]


def test_normalize_strategy_market_dates_rejects_invalid_dates() -> None:
    """Invalid date values should raise an explicit error message."""

    strategy_df = pd.DataFrame({"date": ["not-a-date"], "return": [0.01]})
    market_df = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    with pytest.raises(ValueError, match="Strategy dataframe contains invalid date values"):
        date_prep.normalize_strategy_market_dates(
            strategy_df=strategy_df,
            market_df=market_df,
            interval="1d",
        )
