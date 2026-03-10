"""Strategy builder for trend-following price-action workflows."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from .strategy_models import StrategyBuildRequest, StrategyBuildResult, StrategyRuleSet

REQUIRED_MARKET_COLUMNS: tuple[str, ...] = ("date", "open", "high", "low", "close")

CATEGORY_PRESETS: dict[str, dict[str, float]] = {
    "intraday": {
        "fast_window": 21,
        "slow_window": 55,
        "breakout_window": 20,
        "atr_window": 14,
        "stop_atr_multiplier": 1.6,
        "take_profit_atr_multiplier": 2.8,
    },
    "daily": {
        "fast_window": 20,
        "slow_window": 50,
        "breakout_window": 20,
        "atr_window": 14,
        "stop_atr_multiplier": 1.9,
        "take_profit_atr_multiplier": 3.2,
    },
    "long-term": {
        "fast_window": 13,
        "slow_window": 34,
        "breakout_window": 10,
        "atr_window": 10,
        "stop_atr_multiplier": 2.2,
        "take_profit_atr_multiplier": 3.6,
    },
}


class TrendFollowingBuilder:
    """Construct trend-following strategy artifacts from normalized market data."""

    def _validate_inputs(self, request: StrategyBuildRequest, market_df: pd.DataFrame) -> None:
        """Validate request/category and dataframe prerequisites."""

        if request.category not in CATEGORY_PRESETS:
            raise ValueError(
                f"Unsupported category '{request.category}'. Supported categories: {', '.join(CATEGORY_PRESETS)}"
            )

        missing_columns = [column for column in REQUIRED_MARKET_COLUMNS if column not in market_df.columns]
        if missing_columns:
            missing_str = ", ".join(missing_columns)
            raise ValueError(
                f"Market data is missing required columns for strategy building: {missing_str}"
            )

    def _derive_parameters(self, request: StrategyBuildRequest, market_df: pd.DataFrame) -> dict[str, float | int | None]:
        """Derive strategy parameters from presets plus market context."""

        preset = CATEGORY_PRESETS[request.category]
        slow_window = int(preset["slow_window"])
        min_rows_required = slow_window + 5
        if len(market_df) < min_rows_required:
            raise ValueError(
                f"Not enough market rows to build strategy: got {len(market_df)}, "
                f"need at least {min_rows_required}"
            )

        close = market_df["close"].astype(float)
        high = market_df["high"].astype(float)
        low = market_df["low"].astype(float)

        fast_window = int(preset["fast_window"])
        breakout_window = int(preset["breakout_window"])
        atr_window = int(preset["atr_window"])

        fast_ma = close.rolling(window=fast_window).mean().iloc[-1]
        slow_ma = close.rolling(window=slow_window).mean().iloc[-1]
        rolling_high = high.rolling(window=breakout_window).max().iloc[-1]

        tr = pd.concat(
            [
                (high - low).abs(),
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window=atr_window).mean().iloc[-1]

        trend_strength = ((fast_ma - slow_ma) / slow_ma) if slow_ma else 0.0
        breakout_buffer = max(float(atr) * 0.1, float(close.iloc[-1]) * 0.0005)

        return {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "breakout_window": breakout_window,
            "atr_window": atr_window,
            "stop_atr_multiplier": float(preset["stop_atr_multiplier"]),
            "take_profit_atr_multiplier": float(preset["take_profit_atr_multiplier"]),
            "trend_strength": float(trend_strength),
            "breakout_level": float(rolling_high),
            "breakout_buffer": float(breakout_buffer),
            "atr": float(atr),
            "max_position_value": request.max_position_value,
        }

    def build(self, request: StrategyBuildRequest, market_df: pd.DataFrame) -> StrategyBuildResult:
        """Create a trend-following strategy artifact from market data."""

        self._validate_inputs(request, market_df)
        params = self._derive_parameters(request, market_df)

        rules = StrategyRuleSet(
            name="Trend Following (Price Action)",
            style="trend-following",
            direction="long-only",
            entry_rule=(
                "Enter long when close is above fast moving average and fast moving average is above "
                "slow moving average, then trigger on a breakout above recent swing high plus buffer."
            ),
            exit_rule=(
                "Exit long when close falls below fast moving average or when trend condition "
                "(fast MA above slow MA) is no longer true."
            ),
            stop_loss_rule=(
                "Set stop loss at entry price minus ATR multiplied by stop_atr_multiplier."
            ),
            take_profit_rule=(
                "Set take profit at entry price plus ATR multiplied by take_profit_atr_multiplier."
            ),
        )

        return StrategyBuildResult(
            strategy_id=f"trend_following_{request.ticker.upper()}_{request.interval}",
            generated_at_utc=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            ticker=request.ticker.upper(),
            interval=request.interval,
            category=request.category,
            data_row_count=len(market_df),
            status="generated",
            rules=rules,
            parameters=params,
        )


trend_following_builder = TrendFollowingBuilder()
