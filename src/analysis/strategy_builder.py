"""Strategy builder scaffold for trend-following price-action workflows."""

from __future__ import annotations

import pandas as pd

from .strategy_models import StrategyBuildRequest, StrategyBuildResult

REQUIRED_MARKET_COLUMNS: tuple[str, ...] = ("date", "open", "high", "low", "close")


class TrendFollowingBuilder:
    """Construct trend-following strategy artifacts from normalized market data."""

    def build(self, request: StrategyBuildRequest, market_df: pd.DataFrame) -> StrategyBuildResult:
        """Create a scaffold strategy artifact from market data."""

        missing_columns = [column for column in REQUIRED_MARKET_COLUMNS if column not in market_df.columns]
        if missing_columns:
            missing_str = ", ".join(missing_columns)
            raise ValueError(
                f"Market data is missing required columns for strategy building: {missing_str}"
            )

        return StrategyBuildResult.scaffold(
            ticker=request.ticker,
            interval=request.interval,
            category=request.category,
            data_row_count=len(market_df),
            parameters={"max_position_value": request.max_position_value},
        )


trend_following_builder = TrendFollowingBuilder()
