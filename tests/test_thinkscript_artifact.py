"""Unit tests for ThinkScript artifact path/load/save helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis import thinkscript_artifact
from src.analysis.strategy_models import StrategyBuildResult


def _sample_result(*, ticker: str = "AAPL", interval: str = "1d") -> StrategyBuildResult:
    return StrategyBuildResult.scaffold(
        ticker=ticker,
        interval=interval,
        category="daily",
        data_row_count=42,
        parameters={"fast_window": 20},
    )


def test_save_strategy_artifact_writes_expected_payload(tmp_path: Path) -> None:
    """Saving strategy artifacts should create deterministic JSON output."""

    result = _sample_result(ticker="AAPL", interval="1d")

    output_path = thinkscript_artifact.save_strategy_artifact(result, output_dir=tmp_path)

    assert output_path == tmp_path / "strategy_plan_AAPL_1d.json"
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["strategy_id"] == result.strategy_id
    assert payload["ticker"] == "AAPL"
    assert payload["interval"] == "1d"


def test_load_artifact_payload_optional_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Optional artifact loader should return None when no artifact exists."""

    monkeypatch.setattr(thinkscript_artifact.config, "OUTPUTS_DIR", tmp_path)

    assert thinkscript_artifact.load_artifact_payload_optional(ticker="MSFT", interval="1d") is None


def test_load_artifact_payload_optional_reads_saved_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Optional artifact loader should return payload for existing artifacts."""

    monkeypatch.setattr(thinkscript_artifact.config, "OUTPUTS_DIR", tmp_path)
    result = _sample_result(ticker="NVDA", interval="1d")
    thinkscript_artifact.save_strategy_artifact(result, output_dir=tmp_path)

    payload = thinkscript_artifact.load_artifact_payload_optional(ticker="NVDA", interval="1d")

    assert payload is not None
    assert payload["strategy_id"] == result.strategy_id
