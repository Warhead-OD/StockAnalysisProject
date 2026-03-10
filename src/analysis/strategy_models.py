"""Typed contracts for strategy-construction workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class StrategyBuildRequest:
    """Inputs required to construct a strategy from market data."""

    ticker: str
    interval: str
    category: str
    max_position_value: float | None = None


@dataclass(frozen=True)
class StrategyRuleSet:
    """Human-readable rule definitions for a generated strategy."""

    name: str
    style: str
    direction: str
    entry_rule: str
    exit_rule: str
    stop_loss_rule: str
    take_profit_rule: str


@dataclass(frozen=True)
class StrategyBuildResult:
    """Machine-readable strategy build artifact contract."""

    strategy_id: str
    generated_at_utc: str
    ticker: str
    interval: str
    category: str
    data_row_count: int
    status: str
    rules: StrategyRuleSet
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def scaffold(
        cls,
        *,
        ticker: str,
        interval: str,
        category: str,
        data_row_count: int,
        parameters: dict[str, Any] | None = None,
    ) -> "StrategyBuildResult":
        """Create an initial scaffold result used before full strategy logic exists."""

        strategy_id = f"trend_following_{ticker.upper()}_{interval}"
        return cls(
            strategy_id=strategy_id,
            generated_at_utc=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            ticker=ticker.upper(),
            interval=interval,
            category=category,
            data_row_count=data_row_count,
            status="scaffold",
            rules=StrategyRuleSet(
                name="Trend Following (Price Action)",
                style="trend-following",
                direction="long-only",
                entry_rule="TBD",
                exit_rule="TBD",
                stop_loss_rule="TBD",
                take_profit_rule="TBD",
            ),
            parameters=parameters or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert strategy result to a JSON-serializable dictionary."""

        return asdict(self)
