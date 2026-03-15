"""Scaffold strategy refiner for report-vs-artifact comparison workflows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .strategy_refinement_models import StrategyRefinementRequest, StrategyRefinementResult


def refine_strategy_from_report_scaffold(
    *,
    request: StrategyRefinementRequest,
    strategy_report_df: pd.DataFrame,
    market_df: pd.DataFrame,
    strategy_payload: dict[str, Any] | None,
) -> StrategyRefinementResult:
    """Return a first-pass refinement scaffold summary.

    The current slice only emits an interpretable summary and next-step suggestions.
    Later slices will derive concrete parameter-adjustment recommendations.
    """

    merged_rows = len(strategy_report_df.merge(market_df, on="date", how="inner"))
    strategy_id = str(strategy_payload.get("strategy_id")) if strategy_payload else None

    summary = (
        "Refinement scaffold complete: "
        f"report_rows={len(strategy_report_df)}, market_rows={len(market_df)}, merged_rows={merged_rows}, "
        f"strategy_artifact={'present' if strategy_payload else 'missing'}"
    )

    suggestions = [
        "Compare report drawdown windows against ATR stop multiplier defaults.",
        "Estimate win-rate sensitivity to breakout_lookback and fast/slow MA window changes.",
        "Rank parameter adjustments by impact on risk-adjusted return and max drawdown.",
    ]

    return StrategyRefinementResult.scaffold(
        strategy_name=request.strategy_name,
        ticker=request.ticker,
        interval=request.interval,
        summary=summary,
        suggestions=suggestions,
        strategy_id=strategy_id,
    )
