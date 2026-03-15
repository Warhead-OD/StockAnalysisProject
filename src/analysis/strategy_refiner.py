"""Strategy refiner for report-vs-artifact comparison workflows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .strategy_refinement_models import StrategyRefinementRequest, StrategyRefinementResult


def _as_float(value: object, default: float) -> float:
    """Convert value to float with safe fallback."""

    if isinstance(value, (int, float)):
        return float(value)
    return default


def _as_int(value: object, default: int) -> int:
    """Convert value to int with safe fallback."""

    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _artifact_aware_suggestions(
    *,
    request: StrategyRefinementRequest,
    strategy_report_df: pd.DataFrame,
    strategy_payload: dict[str, Any] | None,
) -> list[str]:
    """Build actionable recommendation bullets using report stats and artifact parameters."""

    if strategy_payload is None:
        return [
            (
                "No generated strategy artifact found for "
                f"{request.ticker.upper()} {request.interval}; run build-strategy first for parameter-aware tuning."
            ),
            "After generating an artifact, compare ATR stop/take-profit multipliers to report drawdown and win-rate.",
            "Track parameter changes per interval to avoid mixing intraday and higher-timeframe tuning assumptions.",
        ]

    params_raw = strategy_payload.get("parameters")
    params = params_raw if isinstance(params_raw, dict) else {}

    fast_window = _as_int(params.get("fast_window"), 20)
    slow_window = _as_int(params.get("slow_window"), 50)
    breakout_window = _as_int(params.get("breakout_window"), 20)
    stop_mult = _as_float(params.get("stop_atr_multiplier"), 1.9)
    tp_mult = _as_float(params.get("take_profit_atr_multiplier"), 3.2)

    returns = strategy_report_df["return"].dropna() if "return" in strategy_report_df.columns else pd.Series(dtype=float)
    mean_return = float(returns.mean()) if not returns.empty else 0.0
    win_rate = float((returns > 0).mean()) if not returns.empty else 0.0

    suggestions: list[str] = [
        (
            "Validate trend filter responsiveness by testing fast/slow windows around "
            f"{fast_window}/{slow_window} for {request.interval} bars."
        ),
        (
            "Re-check breakout sensitivity near lookback="
            f"{breakout_window}; shorter windows react faster but can raise false breakouts."
        ),
    ]

    if win_rate < 0.45:
        suggestions.append(
            "Report win-rate is low; consider slightly wider stops and confirmation filters before entry "
            f"(current stop_atr_multiplier={stop_mult:.2f})."
        )
    elif mean_return > 0:
        suggestions.append(
            "Report expectancy is positive; evaluate scaling take-profit targets "
            f"(current take_profit_atr_multiplier={tp_mult:.2f}) while monitoring drawdown stability."
        )
    else:
        suggestions.append(
            "Report expectancy is weak; test reducing trend lag (faster MA pair) and tighten invalidation rules."
        )

    return suggestions


def refine_strategy_from_report_scaffold(
    *,
    request: StrategyRefinementRequest,
    strategy_report_df: pd.DataFrame,
    market_df: pd.DataFrame,
    strategy_payload: dict[str, Any] | None,
) -> StrategyRefinementResult:
    """Return artifact-aware refinement recommendations for analyze workflows."""

    merged_rows = len(strategy_report_df.merge(market_df, on="date", how="inner"))
    strategy_id = str(strategy_payload.get("strategy_id")) if strategy_payload else None

    summary = (
        "Refinement scaffold complete: "
        f"report_rows={len(strategy_report_df)}, market_rows={len(market_df)}, merged_rows={merged_rows}, "
        f"strategy_artifact={'present' if strategy_payload else 'missing'}"
    )

    suggestions = _artifact_aware_suggestions(
        request=request,
        strategy_report_df=strategy_report_df,
        strategy_payload=strategy_payload,
    )

    return StrategyRefinementResult.scaffold(
        strategy_name=request.strategy_name,
        ticker=request.ticker,
        interval=request.interval,
        summary=summary,
        suggestions=suggestions,
        strategy_id=strategy_id,
    )
