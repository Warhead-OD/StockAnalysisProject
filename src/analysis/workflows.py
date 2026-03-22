"""Reusable analysis workflows decoupled from CLI entrypoints."""

from __future__ import annotations

from .date_prep import normalize_strategy_market_dates
from .strategy_refinement_models import StrategyRefinementResult, StrategyRefinementRequest
from .strategy_refiner import refine_strategy_from_report_scaffold
from .strategy_models import StrategyBuildRequest, StrategyBuildResult


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


def run_build_strategy_workflow(
    *,
    ticker: str,
    interval: str,
    category: str | None = None,
    market_data_access,
) -> StrategyBuildResult:
    """Build strategy from fetched market data in a reusable application workflow.

    Parameters:
    -----------
    ticker : str
        Stock ticker symbol
    interval : str
        Time interval (e.g., '1d', '1h', '15m')
    category : str | None
        Strategy category (e.g., 'daily', 'intraday'). If None, mapped from interval.
    market_data_access
        Data access module with load_metadata() and load_dataset()

    Returns:
    --------
    StrategyBuildResult
        Generated strategy plan artifact.
    """

    from . import map_interval_to_category, trend_following_builder

    # Resolve category from interval if not provided
    resolved_category = category or map_interval_to_category(interval)

    # Build request and execute builder
    build_request = StrategyBuildRequest(
        ticker=ticker,
        interval=interval,
        category=resolved_category,
    )
    result = trend_following_builder.build(build_request, market_data_access.load_dataset(ticker=ticker, interval=interval))

    return result


def run_build_strategy_multi_workflow(
    *,
    tickers: list[str],
    interval: str,
    category: str | None = None,
    market_data_access,
) -> dict[str, dict[str, StrategyBuildResult | str]]:
    """Build strategies for multiple tickers in a reusable batch workflow.

    Processes each ticker independently, capturing per-ticker success/error outcomes.
    Continues processing remaining tickers even if one fails. Returns structured outcomes
    where successful builds are StrategyBuildResult objects and failures are error message strings.

    Parameters:
    -----------
    tickers : list[str]
        List of stock ticker symbols to process
    interval : str
        Time interval (e.g., '1d', '1h', '15m'). Applied to all tickers.
    category : str | None
        Strategy category (e.g., 'daily', 'intraday'). If None, mapped from interval.
        Applied to all tickers.
    market_data_access
        Data access module with load_metadata() and load_dataset()

    Returns:
    --------
    dict[str, dict[str, StrategyBuildResult | str]]
        Outcomes keyed by ticker and interval. For each (ticker, interval) pair:
        - Success: StrategyBuildResult object
        - Failure: Error message string describing the failure
    """

    outcomes: dict[str, dict[str, StrategyBuildResult | str]] = {}

    for ticker in tickers:
        interval_outcomes: dict[str, StrategyBuildResult | str] = {}
        try:
            result = run_build_strategy_workflow(
                ticker=ticker,
                interval=interval,
                category=category,
                market_data_access=market_data_access,
            )
            interval_outcomes[interval] = result
        except Exception as e:
            interval_outcomes[interval] = f"Error building strategy for {ticker}: {str(e)}"

        outcomes[ticker] = interval_outcomes

    return outcomes

