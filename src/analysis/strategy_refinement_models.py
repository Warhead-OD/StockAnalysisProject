"""Typed contracts for report-driven strategy refinement workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class StrategyRefinementRequest:
    """Inputs needed to compare strategy-report performance to generated strategy artifacts."""

    strategy_name: str
    ticker: str
    interval: str


@dataclass(frozen=True)
class StrategyRefinementResult:
    """Machine-readable output for strategy refinement passes."""

    strategy_name: str
    ticker: str
    interval: str
    status: str
    summary: str
    suggestion_count: int
    strategy_id: str | None = None
    suggestions: list[str] = field(default_factory=list)
    refined_at_utc: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )

    @classmethod
    def scaffold(
        cls,
        *,
        strategy_name: str,
        ticker: str,
        interval: str,
        summary: str,
        suggestions: list[str],
        strategy_id: str | None,
    ) -> "StrategyRefinementResult":
        """Create scaffold result for early refinement workflow slices."""

        return cls(
            strategy_name=strategy_name,
            ticker=ticker,
            interval=interval,
            status="scaffold",
            summary=summary,
            suggestion_count=len(suggestions),
            strategy_id=strategy_id,
            suggestions=suggestions,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert refinement result to JSON-serializable dict."""

        return asdict(self)
