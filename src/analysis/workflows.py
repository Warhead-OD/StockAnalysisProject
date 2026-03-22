"""Reusable analysis workflows decoupled from CLI entrypoints."""

from __future__ import annotations

import math

from .date_prep import normalize_strategy_market_dates
from . import thinkscript_artifact
from .strategy_refinement_models import StrategyRefinementResult, StrategyRefinementRequest
from .strategy_refiner import refine_strategy_from_report_scaffold
from .strategy_models import StrategyBuildRequest, StrategyBuildResult

_MERGE_INT_PARAMS = ("fast_window", "slow_window", "breakout_window", "atr_window")
_MERGE_FLOAT_PARAMS = ("stop_atr_multiplier", "take_profit_atr_multiplier")
_ALL_MERGE_PARAMS = _MERGE_INT_PARAMS + _MERGE_FLOAT_PARAMS


def _safe_float(value: object, default: float) -> float:
    """Convert values to float with finite-value guardrails."""

    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    return converted if math.isfinite(converted) else default


def compute_thinkscript_artifact_weight(*, payload: dict[str, object]) -> float:
    """Compute synthetic weight score from artifact metadata and strategy parameters."""

    params = payload.get("parameters")
    if not isinstance(params, dict):
        params = {}

    data_row_count = max(1.0, _safe_float(payload.get("data_row_count", 1), 1.0))
    trend_strength = max(0.0, _safe_float(params.get("trend_strength", 0.0), 0.0))
    fast_window = max(1.0, _safe_float(params.get("fast_window", 20), 20.0))
    slow_window = max(fast_window + 1.0, _safe_float(params.get("slow_window", 50), 50.0))
    breakout_window = max(1.0, _safe_float(params.get("breakout_window", 20), 20.0))
    atr_window = max(1.0, _safe_float(params.get("atr_window", 14), 14.0))
    stop_mult = max(0.1, _safe_float(params.get("stop_atr_multiplier", 1.9), 1.9))
    tp_mult = max(0.1, _safe_float(params.get("take_profit_atr_multiplier", 3.2), 3.2))

    reward_risk = tp_mult / stop_mult
    trend_component = 1.0 + min(trend_strength * 10.0, 1.0)
    smoothness_component = slow_window / fast_window
    volatility_component = 1.0 + (breakout_window / atr_window) * 0.1
    category = str(payload.get("category", "")).lower()
    category_component = {"intraday": 1.0, "daily": 1.05, "long-term": 1.1}.get(category, 1.0)

    score = data_row_count * reward_risk * trend_component * smoothness_component * volatility_component
    return max(0.001, score * category_component)


def run_merge_thinkscript_artifacts_workflow(
    *,
    tickers: list[str],
    interval: str,
) -> dict[str, object]:
    """Merge strategy artifacts into a single weighted payload for multi-ticker ThinkScript export."""

    loaded_payloads: dict[str, dict[str, object]] = {}
    skipped: dict[str, str] = {}

    for ticker in tickers:
        payload = thinkscript_artifact.load_artifact_payload_optional(ticker=ticker, interval=interval)
        if payload is None:
            skipped[ticker] = f"Strategy artifact not found for {ticker} ({interval})"
            continue
        loaded_payloads[ticker] = payload

    if not loaded_payloads:
        raise ValueError("No strategy artifacts were found for the requested tickers and interval")

    categories = {str(payload.get("category", "")).lower() for payload in loaded_payloads.values()}
    if len(categories) != 1:
        raise ValueError("All tickers must share the same strategy category for multi-ticker export")

    intervals = {str(payload.get("interval", "")).lower() for payload in loaded_payloads.values()}
    if len(intervals) != 1 or interval.lower() not in intervals:
        raise ValueError("All tickers must share the requested interval for multi-ticker export")

    raw_scores = {
        ticker: compute_thinkscript_artifact_weight(payload=payload)
        for ticker, payload in loaded_payloads.items()
    }
    score_total = sum(raw_scores.values())
    if score_total <= 0:
        raise ValueError("Unable to compute positive weights from strategy artifacts")

    weights = {ticker: score / score_total for ticker, score in raw_scores.items()}

    weighted: dict[str, float] = {key: 0.0 for key in _ALL_MERGE_PARAMS}
    defaults: dict[str, float] = {
        "fast_window": 20.0,
        "slow_window": 50.0,
        "breakout_window": 20.0,
        "atr_window": 14.0,
        "stop_atr_multiplier": 1.9,
        "take_profit_atr_multiplier": 3.2,
    }

    for ticker, payload in loaded_payloads.items():
        params = payload.get("parameters")
        param_dict = params if isinstance(params, dict) else {}
        ticker_weight = weights[ticker]
        for key in _ALL_MERGE_PARAMS:
            weighted[key] += _safe_float(param_dict.get(key, defaults[key]), defaults[key]) * ticker_weight

    merged_fast = max(2, int(round(weighted["fast_window"])))
    merged_slow = max(merged_fast + 1, int(round(weighted["slow_window"])))
    merged_breakout = max(2, int(round(weighted["breakout_window"])))
    merged_atr = max(2, int(round(weighted["atr_window"])))
    merged_stop = round(max(0.1, weighted["stop_atr_multiplier"]), 4)
    merged_tp = round(max(0.1, weighted["take_profit_atr_multiplier"]), 4)

    category = next(iter(categories))
    merged_payload: dict[str, object] = {
        "strategy_id": f"trend_following_MULTI_{interval}",
        "ticker": "MULTI",
        "interval": interval,
        "category": category,
        "status": "generated",
        "data_row_count": int(sum(_safe_float(p.get("data_row_count", 0), 0.0) for p in loaded_payloads.values())),
        "merged_tickers": list(loaded_payloads.keys()),
        "skipped_tickers": skipped,
        "weights": weights,
        "weight_scores": raw_scores,
        "parameters": {
            "fast_window": merged_fast,
            "slow_window": merged_slow,
            "breakout_window": merged_breakout,
            "atr_window": merged_atr,
            "stop_atr_multiplier": merged_stop,
            "take_profit_atr_multiplier": merged_tp,
        },
    }

    return merged_payload


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

