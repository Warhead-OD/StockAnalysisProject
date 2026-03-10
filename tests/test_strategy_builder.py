"""Unit tests for trend-following strategy builder."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis import StrategyBuildRequest, trend_following_builder


def _market_df(rows: int = 90) -> pd.DataFrame:
    """Create normalized OHLC market data for strategy-builder tests."""

    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "open": [100.0 + idx * 0.3 for idx in range(rows)],
            "high": [100.8 + idx * 0.3 for idx in range(rows)],
            "low": [99.2 + idx * 0.3 for idx in range(rows)],
            "close": [100.4 + idx * 0.3 for idx in range(rows)],
            "adj_close": [100.4 + idx * 0.3 for idx in range(rows)],
        }
    )


def test_trend_following_builder_generates_result() -> None:
    """Builder returns a generated trend-following strategy artifact for valid input."""

    request = StrategyBuildRequest(ticker="AAPL", interval="1d", category="daily", max_position_value=5000.0)

    result = trend_following_builder.build(request=request, market_df=_market_df())

    assert result.status == "generated"
    assert result.strategy_id == "trend_following_AAPL_1d"
    assert result.ticker == "AAPL"
    assert result.interval == "1d"
    assert result.category == "daily"
    assert result.data_row_count == 90
    assert result.rules.style == "trend-following"
    assert result.rules.direction == "long-only"
    assert result.parameters["fast_window"] == 20
    assert result.parameters["slow_window"] == 50
    assert result.parameters["max_position_value"] == 5000.0


def test_trend_following_builder_rejects_missing_columns() -> None:
    """Builder raises when required OHLC columns are missing."""

    request = StrategyBuildRequest(ticker="AAPL", interval="1d", category="daily")
    bad_df = pd.DataFrame({"date": ["2026-01-01"], "close": [100.0]})

    with pytest.raises(ValueError, match="missing required columns"):
        trend_following_builder.build(request=request, market_df=bad_df)


def test_trend_following_builder_rejects_short_dataset() -> None:
    """Builder raises when there are too few rows for rolling-window calculations."""

    request = StrategyBuildRequest(ticker="AAPL", interval="1d", category="daily")

    with pytest.raises(ValueError, match="Not enough market rows"):
        trend_following_builder.build(request=request, market_df=_market_df(rows=20))


def test_trend_following_builder_rejects_unknown_category() -> None:
    """Builder raises on unsupported strategy category values."""

    request = StrategyBuildRequest(ticker="AAPL", interval="1d", category="swing")

    with pytest.raises(ValueError, match="Unsupported category"):
        trend_following_builder.build(request=request, market_df=_market_df())
