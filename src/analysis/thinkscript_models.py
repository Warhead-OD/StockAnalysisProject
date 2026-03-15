"""Typed contracts for ThinkScript export workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ThinkScriptExportRequest:
    """Inputs for exporting ThinkScript from a strategy artifact."""

    ticker: str
    interval: str
    export_mode: str = "strategy"
    include_orders: bool = True


@dataclass(frozen=True)
class ThinkScriptExportResult:
    """Result metadata for a ThinkScript export operation."""

    ticker: str
    interval: str
    export_mode: str
    include_orders: bool
    output_path: str
    exported_at_utc: str
    status: str
    strategy_id: str | None = None

    @classmethod
    def scaffold(
        cls,
        *,
        ticker: str,
        interval: str,
        export_mode: str,
        include_orders: bool,
        output_path: str,
        strategy_id: str | None,
    ) -> "ThinkScriptExportResult":
        """Create a scaffold export result (status=scaffold)."""

        return cls(
            ticker=ticker,
            interval=interval,
            export_mode=export_mode,
            include_orders=include_orders,
            output_path=output_path,
            exported_at_utc=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            status="scaffold",
            strategy_id=strategy_id,
        )

    @classmethod
    def generated(
        cls,
        *,
        ticker: str,
        interval: str,
        export_mode: str,
        include_orders: bool,
        output_path: str,
        strategy_id: str | None,
        generated_at: str,
    ) -> "ThinkScriptExportResult":
        """Create a result for a fully rendered ThinkScript export (status=generated)."""

        return cls(
            ticker=ticker,
            interval=interval,
            export_mode=export_mode,
            include_orders=include_orders,
            output_path=output_path,
            exported_at_utc=generated_at,
            status="generated",
            strategy_id=strategy_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert export result to JSON-serializable dict."""

        return asdict(self)
