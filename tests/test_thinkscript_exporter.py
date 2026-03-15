"""Unit tests for ThinkScript template rendering and export function."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.thinkscript_exporter import _build_thinkscript_source, export_thinkscript_scaffold
from src.analysis.thinkscript_models import ThinkScriptExportRequest


def _sample_payload(
    *,
    ticker: str = "AAPL",
    interval: str = "1d",
    fast_window: int = 20,
    slow_window: int = 50,
) -> dict[str, object]:
    """Minimal strategy artifact payload for exporter unit tests."""

    return {
        "strategy_id": f"trend_following_{ticker.upper()}_{interval}",
        "ticker": ticker,
        "interval": interval,
        "status": "generated",
        "parameters": {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "breakout_window": 20,
            "atr_window": 14,
            "stop_atr_multiplier": 1.9,
            "take_profit_atr_multiplier": 3.2,
        },
    }


def _strategy_request(
    *,
    ticker: str = "AAPL",
    interval: str = "1d",
    export_mode: str = "strategy",
    include_orders: bool = True,
) -> ThinkScriptExportRequest:
    return ThinkScriptExportRequest(
        ticker=ticker,
        interval=interval,
        export_mode=export_mode,
        include_orders=include_orders,
    )


# ── _build_thinkscript_source unit tests ─────────────────────────────────────


def test_build_source_contains_input_declarations() -> None:
    """Rendered source includes ThinkScript input declarations for all parameters."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(fast_window=21, slow_window=55),
        request=_strategy_request(),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "input fast_length       = 21;" in source
    assert "input slow_length       = 55;" in source
    assert "input breakout_lookback = 20;" in source
    assert "input atr_length        = 14;" in source
    assert "input stop_atr_mult     = 1.9;" in source
    assert "input tp_atr_mult       = 3.2;" in source


def test_build_source_contains_signal_plots() -> None:
    """Rendered source includes BuyArrow, SellArrow, FastMALine, SlowMALine plots."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(),
        request=_strategy_request(),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "plot BuyArrow" in source
    assert "plot SellArrow" in source
    assert "plot FastMALine" in source
    assert "plot SlowMALine" in source
    assert "declare upper;" in source


def test_build_source_emits_add_order_for_strategy_mode_with_orders() -> None:
    """AddOrder lines are present when export_mode=strategy and include_orders=True."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(),
        request=_strategy_request(export_mode="strategy", include_orders=True),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "AddOrder" in source
    assert "BUY_TO_OPEN" in source
    assert "SELL_TO_CLOSE" in source


def test_build_source_suppresses_add_order_when_orders_disabled() -> None:
    """AddOrder lines are absent when include_orders=False."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(),
        request=_strategy_request(export_mode="strategy", include_orders=False),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "AddOrder" not in source


def test_build_source_suppresses_add_order_for_study_mode() -> None:
    """AddOrder lines are absent when export_mode=study even with include_orders=True."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(),
        request=_strategy_request(export_mode="study", include_orders=True),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "AddOrder" not in source


def test_build_source_header_contains_ticker_interval_mode() -> None:
    """Source header comment includes ticker, interval, and mode metadata."""

    source = _build_thinkscript_source(
        strategy_payload=_sample_payload(ticker="SPY", interval="1wk"),
        request=_strategy_request(ticker="SPY", interval="1wk", export_mode="study"),
        generated_at="2026-03-15T00:00:00Z",
    )

    assert "ticker=SPY" in source
    assert "interval=1wk" in source
    assert "mode=study" in source


# ── export_thinkscript_scaffold integration tests ────────────────────────────


def test_export_thinkscript_scaffold_writes_file_and_returns_generated_result(
    tmp_path: Path,
) -> None:
    """export_thinkscript_scaffold writes a .txt file and returns status=generated."""

    artifact = tmp_path / "strategy_plan_AAPL_1d.json"
    artifact.write_text(json.dumps(_sample_payload()), encoding="utf-8")
    output = tmp_path / "thinkscript_AAPL_1d_strategy.txt"

    result = export_thinkscript_scaffold(
        request=_strategy_request(),
        strategy_artifact_path=artifact,
        output_path=output,
    )

    assert output.exists()
    written_source = output.read_text(encoding="utf-8")
    assert "declare upper;" in written_source
    assert "plot BuyArrow" in written_source

    assert result.status == "generated"
    assert result.ticker == "AAPL"
    assert result.interval == "1d"
    assert result.export_mode == "strategy"
    assert result.strategy_id == "trend_following_AAPL_1d"
    assert result.output_path == str(output)


def test_export_thinkscript_scaffold_missing_artifact_raises(tmp_path: Path) -> None:
    """export_thinkscript_scaffold raises FileNotFoundError when artifact is absent."""

    missing = tmp_path / "strategy_plan_MISSING_1d.json"
    output = tmp_path / "thinkscript_MISSING_1d_strategy.txt"

    with pytest.raises(FileNotFoundError, match="Strategy artifact not found"):
        export_thinkscript_scaffold(
            request=_strategy_request(ticker="MISSING"),
            strategy_artifact_path=missing,
            output_path=output,
        )


def test_export_thinkscript_scaffold_creates_output_directory(tmp_path: Path) -> None:
    """export_thinkscript_scaffold creates missing parent directories for the output file."""

    artifact = tmp_path / "strategy_plan_AAPL_1d.json"
    artifact.write_text(json.dumps(_sample_payload()), encoding="utf-8")
    nested_output = tmp_path / "nested" / "deep" / "thinkscript_AAPL_1d_strategy.txt"

    export_thinkscript_scaffold(
        request=_strategy_request(),
        strategy_artifact_path=artifact,
        output_path=nested_output,
    )

    assert nested_output.exists()
