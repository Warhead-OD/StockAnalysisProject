"""Typed models for market-data fetch and storage operations."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class MarketFetchRequest:
    """Inputs required to fetch market data from yfinance."""

    ticker: str
    start: str | None = None
    end: str | None = None
    period: str | None = None
    interval: str = "1d"
    auto_adjust: bool = False
    prepost: bool = False
    actions: bool = False


@dataclass(frozen=True)
class MarketDatasetMetadata:
    """Metadata describing one fetched market dataset artifact."""

    ticker: str
    interval: str
    period: str | None
    start: str | None
    end: str | None
    auto_adjust: bool
    prepost: bool
    actions: bool
    exchange_timezone: str
    fetched_at_utc: str
    row_count: int

    @classmethod
    def from_request(
        cls,
        request: MarketFetchRequest,
        *,
        row_count: int,
        exchange_timezone: str = "America/New_York",
    ) -> "MarketDatasetMetadata":
        """Build metadata from a fetch request plus runtime fetch stats."""

        return cls(
            ticker=request.ticker,
            interval=request.interval,
            period=request.period,
            start=request.start,
            end=request.end,
            auto_adjust=request.auto_adjust,
            prepost=request.prepost,
            actions=request.actions,
            exchange_timezone=exchange_timezone,
            fetched_at_utc=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            row_count=row_count,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert metadata to a JSON-serializable dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarketDatasetMetadata":
        """Create typed metadata from a decoded JSON payload."""

        row_count_value = payload.get("row_count")
        if isinstance(row_count_value, bool) or not isinstance(row_count_value, (int, float, str)):
            raise ValueError("Invalid row_count in market metadata payload")

        return cls(
            ticker=str(payload["ticker"]),
            interval=str(payload["interval"]),
            period=str(payload["period"]) if payload.get("period") is not None else None,
            start=str(payload["start"]) if payload.get("start") is not None else None,
            end=str(payload["end"]) if payload.get("end") is not None else None,
            auto_adjust=bool(payload["auto_adjust"]),
            prepost=bool(payload["prepost"]),
            actions=bool(payload["actions"]),
            exchange_timezone=str(payload["exchange_timezone"]),
            fetched_at_utc=str(payload["fetched_at_utc"]),
            row_count=int(row_count_value),
        )
