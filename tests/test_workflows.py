"""Unit tests for reusable analysis workflows."""

from __future__ import annotations

import pandas as pd
import pytest

from src import analysis
from src.analysis import workflows


def _strategy_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "return": [0.01, -0.02],
        }
    )


def _market_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "adj_close": [100.0, 99.0],
        }
    )


def test_run_analyze_workflow_returns_metrics_and_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow should return metric output and scaffold refinement output together."""

    expected_metrics = {"sharpe_ratio": 1.25}
    expected_refinement = analysis.StrategyRefinementResult.scaffold(
        strategy_name="demo",
        ticker="AAPL",
        interval="1d",
        summary="ok",
        suggestions=["one"],
        strategy_id="trend_following_AAPL_1d",
    )

    monkeypatch.setattr(analysis.metrics, "compute_all", lambda _df: expected_metrics)
    monkeypatch.setattr(
        workflows,
        "refine_strategy_from_report_scaffold",
        lambda **_kwargs: expected_refinement,
    )

    metrics_result, refinement_result = workflows.run_analyze_workflow(
        strategy_name="demo",
        ticker="AAPL",
        interval="1d",
        strategy_df=_strategy_df(),
        market_df=_market_df(),
        strategy_payload={"strategy_id": "trend_following_AAPL_1d"},
    )

    assert metrics_result == expected_metrics
    assert refinement_result == expected_refinement


def test_run_analyze_workflow_normalizes_dates_for_intraday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow should normalize intraday date keys before merging and refinement."""

    strategy_df = pd.DataFrame(
        {
            "date": ["2026-01-01 09:30:00", "2026-01-01 09:45:00"],
            "return": [0.01, -0.02],
        }
    )
    market_df = pd.DataFrame(
        {
            "date": ["2026-01-01 09:30:00", "2026-01-01 09:45:00"],
            "adj_close": [100.0, 99.0],
        }
    )

    monkeypatch.setattr(analysis.metrics, "compute_all", lambda _df: {"sharpe_ratio": 0.5})
    monkeypatch.setattr(
        workflows,
        "refine_strategy_from_report_scaffold",
        lambda **_kwargs: analysis.StrategyRefinementResult.scaffold(
            strategy_name="demo",
            ticker="AAPL",
            interval="15m",
            summary="ok",
            suggestions=["one"],
            strategy_id="trend_following_AAPL_15m",
        ),
    )

    metrics_result, refinement_result = workflows.run_analyze_workflow(
        strategy_name="demo",
        ticker="AAPL",
        interval="15m",
        strategy_df=strategy_df,
        market_df=market_df,
        strategy_payload={"strategy_id": "trend_following_AAPL_15m"},
    )

    assert metrics_result["sharpe_ratio"] == 0.5
    assert refinement_result.interval == "15m"


def test_run_build_strategy_workflow_returns_strategy_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow should build strategy and return StrategyBuildResult."""

    # Mock market data access
    mock_market_data = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "adj_close": [101.0, 102.0],
        }
    )

    class MockMarketDataAccess:
        def load_dataset(self, *, ticker, interval):
            return mock_market_data

    mock_access = MockMarketDataAccess()
    expected_result = analysis.StrategyBuildResult.scaffold(
        ticker="AAPL",
        interval="1d",
        category="daily",
        data_row_count=2,
    )

    monkeypatch.setattr(
        analysis.trend_following_builder,
        "build",
        lambda _request, _dataset: expected_result,
    )

    result = workflows.run_build_strategy_workflow(
        ticker="AAPL",
        interval="1d",
        category="daily",
        market_data_access=mock_access,
    )

    assert result.strategy_id == expected_result.strategy_id
    assert result.status == expected_result.status
    assert result.data_row_count == expected_result.data_row_count


def test_run_build_strategy_workflow_maps_interval_to_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow should derive category from interval when not provided."""

    class MockMarketDataAccess:
        def load_dataset(self, *, ticker, interval):
            return pd.DataFrame({"close": [100.0, 101.0]})

    mock_access = MockMarketDataAccess()
    captured_request = {}

    def fake_build(request, _dataset):
        captured_request["category"] = request.category
        return analysis.StrategyBuildResult.scaffold(
            ticker="AAPL",
            interval="1h",
            category="intraday",
            data_row_count=2,
        )

    monkeypatch.setattr(analysis.trend_following_builder, "build", fake_build)

    result = workflows.run_build_strategy_workflow(
        ticker="AAPL",
        interval="1h",
        market_data_access=mock_access,
    )

    assert captured_request["category"] == "intraday"
    assert result.strategy_id == "trend_following_AAPL_1h"


def test_run_build_strategy_multi_workflow_returns_per_ticker_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-ticker workflow should return dict of outcomes keyed by ticker and interval."""

    class MockMarketDataAccess:
        def load_dataset(self, *, ticker, interval):
            return pd.DataFrame({"close": [100.0, 101.0]})

    mock_access = MockMarketDataAccess()
    expected_result = analysis.StrategyBuildResult.scaffold(
        ticker="AAPL",
        interval="1d",
        category="daily",
        data_row_count=2,
    )

    monkeypatch.setattr(
        analysis.trend_following_builder,
        "build",
        lambda _request, _dataset: expected_result,
    )

    outcomes = workflows.run_build_strategy_multi_workflow(
        tickers=["AAPL", "MSFT"],
        interval="1d",
        category="daily",
        market_data_access=mock_access,
    )

    assert "AAPL" in outcomes
    assert "MSFT" in outcomes
    assert "1d" in outcomes["AAPL"]
    assert "1d" in outcomes["MSFT"]
    assert isinstance(outcomes["AAPL"]["1d"], analysis.StrategyBuildResult)
    assert isinstance(outcomes["MSFT"]["1d"], analysis.StrategyBuildResult)


def test_run_build_strategy_multi_workflow_continues_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-ticker workflow should continue processing after failure and capture error message."""

    class MockMarketDataAccess:
        def load_dataset(self, *, ticker, interval):
            if ticker == "AAPL":
                return pd.DataFrame({"close": [100.0, 101.0]})
            else:
                raise ValueError("Missing data for MSFT")

    mock_access = MockMarketDataAccess()
    expected_result = analysis.StrategyBuildResult.scaffold(
        ticker="AAPL",
        interval="1d",
        category="daily",
        data_row_count=2,
    )

    monkeypatch.setattr(
        analysis.trend_following_builder,
        "build",
        lambda _request, _dataset: expected_result,
    )

    outcomes = workflows.run_build_strategy_multi_workflow(
        tickers=["AAPL", "MSFT"],
        interval="1d",
        category="daily",
        market_data_access=mock_access,
    )

    # AAPL should succeed
    assert isinstance(outcomes["AAPL"]["1d"], analysis.StrategyBuildResult)
    assert outcomes["AAPL"]["1d"].ticker == "AAPL"

    # MSFT should have error message
    assert isinstance(outcomes["MSFT"]["1d"], str)
    assert "Error building strategy for MSFT" in outcomes["MSFT"]["1d"]
    assert "Missing data for MSFT" in outcomes["MSFT"]["1d"]


def test_run_build_strategy_multi_workflow_single_ticker_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-ticker workflow with single-ticker input should behave identically to single-ticker workflow."""

    class MockMarketDataAccess:
        def load_dataset(self, *, ticker, interval):
            return pd.DataFrame({"close": [100.0, 101.0]})

    mock_access = MockMarketDataAccess()
    expected_result = analysis.StrategyBuildResult.scaffold(
        ticker="NVDA",
        interval="1h",
        category="intraday",
        data_row_count=2,
    )

    monkeypatch.setattr(
        analysis.trend_following_builder,
        "build",
        lambda _request, _dataset: expected_result,
    )

    single_outcome = workflows.run_build_strategy_multi_workflow(
        tickers=["NVDA"],
        interval="1h",
        category="intraday",
        market_data_access=mock_access,
    )

    assert "NVDA" in single_outcome
    assert "1h" in single_outcome["NVDA"]
    assert isinstance(single_outcome["NVDA"]["1h"], analysis.StrategyBuildResult)
    assert single_outcome["NVDA"]["1h"].ticker == "NVDA"
    assert single_outcome["NVDA"]["1h"].interval == "1h"


