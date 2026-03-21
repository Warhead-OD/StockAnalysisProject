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
