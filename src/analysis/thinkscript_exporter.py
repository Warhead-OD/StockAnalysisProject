"""ThinkScript exporter scaffold.

This module will evolve into a rule-driven exporter that converts strategy JSON
artifacts into ThinkScript-compatible strategy/study scripts.
"""

from __future__ import annotations

import json
from pathlib import Path

from .thinkscript_models import ThinkScriptExportRequest, ThinkScriptExportResult


def _build_scaffold_source(
    *,
    strategy_payload: dict[str, object],
    request: ThinkScriptExportRequest,
) -> str:
    """Render a minimal scaffold ThinkScript body from strategy payload."""

    strategy_id = str(strategy_payload.get("strategy_id", "unknown_strategy"))
    return (
        f"# ThinkScript scaffold for {strategy_id}\n"
        f"# ticker={request.ticker} interval={request.interval} mode={request.export_mode}\n"
        "# NOTE: Full rule-based export will be implemented in later sub-slices.\n"
        "declare upper;\n"
        "\n"
        "# Placeholder signal output\n"
        "plot Signal = Double.NaN;\n"
    )


def export_thinkscript_scaffold(
    *,
    request: ThinkScriptExportRequest,
    strategy_artifact_path: Path,
    output_path: Path,
) -> ThinkScriptExportResult:
    """Export a scaffold ThinkScript text file from a strategy artifact."""

    if not strategy_artifact_path.exists():
        raise FileNotFoundError(
            f"Strategy artifact not found: {strategy_artifact_path}. "
            "Run build-strategy before export-thinkscript."
        )

    payload = json.loads(strategy_artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid strategy artifact format in {strategy_artifact_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    source = _build_scaffold_source(strategy_payload=payload, request=request)
    output_path.write_text(source, encoding="utf-8")

    return ThinkScriptExportResult.scaffold(
        ticker=request.ticker,
        interval=request.interval,
        export_mode=request.export_mode,
        include_orders=request.include_orders,
        output_path=str(output_path),
        strategy_id=str(payload.get("strategy_id")) if payload.get("strategy_id") else None,
    )
