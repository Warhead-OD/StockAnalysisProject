"""Reusable analysis workflows decoupled from CLI entrypoints."""

from __future__ import annotations

from .date_prep import normalize_strategy_market_dates
from .strategy_refinement_models import StrategyRefinementResult, StrategyRefinementRequest
from .strategy_refiner import refine_strategy_from_report_scaffold


def run_analyze_workflow(
    *,
    strategy_name: str,
    ticker: str,
    interval: str,
    strategy_df,
    market_df,
    strategy_payload: dict[str, object] | None,
) -> tuple[dict[str, float], StrategyRefinementResult]:
    """Run interval-aware metrics and refinement in a reusable application workflow."""

    from . import metrics

    normalized_strategy_df, normalized_market_df = normalize_strategy_market_dates(
        strategy_df=strategy_df,
        market_df=market_df,
        interval=interval,
    )
    merged = normalized_strategy_df.merge(normalized_market_df, on="date")

    metric_values = metrics.compute_all(merged)

    refinement_request = StrategyRefinementRequest(
        strategy_name=strategy_name,
        ticker=ticker,
        interval=interval,
    )
    refinement = refine_strategy_from_report_scaffold(
        request=refinement_request,
        strategy_report_df=normalized_strategy_df,
        market_df=normalized_market_df,
        strategy_payload=strategy_payload,
    )

    return metric_values, refinement
