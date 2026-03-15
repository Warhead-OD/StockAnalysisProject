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
    assert "fast/slow windows" in result.suggestions[0]
    assert "lookback=20" in result.suggestions[1]


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
    assert "No generated strategy artifact found" in result.suggestions[0]


def test_refine_strategy_from_report_scaffold_low_win_rate_branch() -> None:
    """Low win-rate report data should produce defensive stop/entry recommendation text."""

    request = StrategyRefinementRequest(strategy_name="demo", ticker="SPY", interval="1d")
    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"], "return": [-0.02, -0.01, 0.01]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"], "adj_close": [100.0, 99.0, 100.5]})

    result = refine_strategy_from_report_scaffold(
        request=request,
        strategy_report_df=strategy_df,
        market_df=market_df,
        strategy_payload={"strategy_id": "trend_following_SPY_1d", "parameters": {"stop_atr_multiplier": 2.1}},
    )

    assert "win-rate is low" in result.suggestions[2]
    assert "stop_atr_multiplier=2.10" in result.suggestions[2]


def test_refine_strategy_from_report_scaffold_positive_expectancy_branch() -> None:
    """Positive expectancy with acceptable win rate should suggest take-profit scaling checks."""

    request = StrategyRefinementRequest(strategy_name="demo", ticker="SPY", interval="1d")
    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"], "return": [0.03, -0.01, 0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"], "adj_close": [100.0, 99.5, 101.0]})

    result = refine_strategy_from_report_scaffold(
        request=request,
        strategy_report_df=strategy_df,
        market_df=market_df,
        strategy_payload={"strategy_id": "trend_following_SPY_1d", "parameters": {"take_profit_atr_multiplier": 3.6}},
    )

    assert "expectancy is positive" in result.suggestions[2]
    assert "take_profit_atr_multiplier=3.60" in result.suggestions[2]


def test_refine_strategy_from_report_scaffold_uses_defaults_for_invalid_parameter_types() -> None:
    """Invalid parameter types in artifact payload should safely fall back to default tuning values."""

    request = StrategyRefinementRequest(strategy_name="demo", ticker="SPY", interval="1d")
    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"], "return": [0.01, -0.02, 0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"], "adj_close": [100.0, 99.0, 100.0, 98.0]})

    result = refine_strategy_from_report_scaffold(
        request=request,
        strategy_report_df=strategy_df,
        market_df=market_df,
        strategy_payload={
            "strategy_id": "trend_following_SPY_1d",
            "parameters": {
                "fast_window": "bad",
                "slow_window": "bad",
                "breakout_window": "bad",
            },
        },
    )

    assert "20/50" in result.suggestions[0]
    assert "lookback=20" in result.suggestions[1]
    assert "expectancy is weak" in result.suggestions[2]
