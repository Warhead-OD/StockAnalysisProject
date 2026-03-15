"""
Analysis utilities.

Currently implements a few basic return‑based metrics.
"""

from __future__ import annotations

import pandas as pd

from .strategy_builder import trend_following_builder
from .strategy_models import StrategyBuildRequest, StrategyBuildResult
from .thinkscript_exporter import export_thinkscript_scaffold
from .thinkscript_models import ThinkScriptExportRequest, ThinkScriptExportResult

__all__ = [
    "metrics",
    "trend_following_builder",
    "StrategyBuildRequest",
    "StrategyBuildResult",
    "ThinkScriptExportRequest",
    "ThinkScriptExportResult",
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
        returns = df["return"].dropna()
        annualized_return = (1 + returns.mean()) ** 252 - 1
        volatility = returns.std() * (252 ** 0.5)
        sharpe = annualized_return / volatility if volatility else float("nan")

        return {
            "daily_mean_return": returns.mean(),
            "annualized_return": annualized_return,
            "annualized_volatility": volatility,
            "sharpe_ratio": sharpe,
        }

metrics = _MetricsModule()
