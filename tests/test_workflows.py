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

