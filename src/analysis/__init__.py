"""Analysis utilities.

Currently implements a few basic return‑based metrics.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["metrics"]

class _MetricsModule:
    def compute_all(self, df: pd.DataFrame) -> dict[str, float]:
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
