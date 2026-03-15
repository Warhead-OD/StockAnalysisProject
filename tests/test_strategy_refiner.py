"""Unit tests for report-driven strategy refinement scaffold."""

from __future__ import annotations

import pandas as pd

from src.analysis import StrategyRefinementRequest, refine_strategy_from_report_scaffold


def test_refine_strategy_from_report_scaffold_with_artifact() -> None:
    """Refinement scaffold includes artifact context when strategy payload is present."""

    request = StrategyRefinementRequest(strategy_name="demo", ticker="SPY", interval="1d")
    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    result = refine_strategy_from_report_scaffold(
        request=request,
        strategy_report_df=strategy_df,
        market_df=market_df,
        strategy_payload={"strategy_id": "trend_following_SPY_1d"},
    )

    assert result.status == "scaffold"
    assert result.strategy_id == "trend_following_SPY_1d"
    assert result.suggestion_count == 3
    assert "strategy_artifact=present" in result.summary


def test_refine_strategy_from_report_scaffold_without_artifact() -> None:
    """Refinement scaffold remains valid when no strategy artifact is available."""

    request = StrategyRefinementRequest(strategy_name="demo", ticker="SPY", interval="1d")
    strategy_df = pd.DataFrame({"date": ["2026-01-01"], "return": [0.01]})
    market_df = pd.DataFrame({"date": ["2026-01-02"], "adj_close": [99.0]})

    result = refine_strategy_from_report_scaffold(
        request=request,
        strategy_report_df=strategy_df,
        market_df=market_df,
        strategy_payload=None,
    )

    assert result.status == "scaffold"
    assert result.strategy_id is None
    assert result.suggestion_count == 3
    assert "merged_rows=0" in result.summary
    assert "strategy_artifact=missing" in result.summary
