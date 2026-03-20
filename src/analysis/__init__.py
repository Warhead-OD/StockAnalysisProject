"""
Analysis utilities.

Currently implements a few basic return‑based metrics.
"""

from __future__ import annotations

import math

import pandas as pd

from .strategy_builder import trend_following_builder
from .date_prep import map_interval_to_category, normalize_strategy_market_dates
from .strategy_models import StrategyBuildRequest, StrategyBuildResult
from .strategy_refiner import refine_strategy_from_report_scaffold
from .strategy_refinement_models import StrategyRefinementRequest, StrategyRefinementResult
from .thinkscript_exporter import export_thinkscript, export_thinkscript_scaffold
from .thinkscript_models import ThinkScriptExportRequest, ThinkScriptExportResult

__all__ = [
    "metrics",
    "trend_following_builder",
    "map_interval_to_category",
    "normalize_strategy_market_dates",
    "StrategyBuildRequest",
    "StrategyBuildResult",
    "StrategyRefinementRequest",
    "StrategyRefinementResult",
    "refine_strategy_from_report_scaffold",
    "ThinkScriptExportRequest",
    "ThinkScriptExportResult",
    "export_thinkscript",
    "export_thinkscript_scaffold",
]


class _MetricsModule:
    """
    Provides methods for computing financial metrics from strategy and market data.
    """

    def compute_all(self, df: pd.DataFrame) -> dict[str, float]:
        """
        Compute key financial metrics from a DataFrame.

        Expects columns: "date", "return", "adj_close".

        Args:
            df (pd.DataFrame): DataFrame containing strategy and market data.

        Returns:
            dict[str, float]: Dictionary of computed metrics including daily mean return, annualized return, volatility, and Sharpe ratio.

        Raises:
            ValueError: If the 'return' column is missing.
        """
        
        # Expecting df to have columns: "date", "return", "adj_close"
        if "return" not in df.columns:
            raise ValueError("DataFrame must contain a 'return' column for strategy returns")

        # Daily returns
        returns = pd.to_numeric(df["return"], errors="coerce").dropna()
        daily_mean = float(returns.mean()) if not returns.empty else float("nan")

        # Use log/expm1 formulation and guard invalid domains to avoid overflow warnings.
        if math.isfinite(daily_mean) and daily_mean > -1:
            annualized_return = math.expm1(math.log1p(daily_mean) * 252)
        else:
            annualized_return = float("nan")

        volatility = float(returns.std() * (252 ** 0.5)) if not returns.empty else float("nan")
        sharpe = (
            annualized_return / volatility
            if math.isfinite(annualized_return) and math.isfinite(volatility) and volatility > 0
            else float("nan")
        )

        return {
            "daily_mean_return": daily_mean,
            "annualized_return": annualized_return,
            "annualized_volatility": volatility,
            "sharpe_ratio": sharpe,
        }

metrics = _MetricsModule()
