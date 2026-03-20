"""ThinkScript artifact resolution and loading utilities."""

from __future__ import annotations

import json
from pathlib import Path

from .. import config

# Artifact naming constants
STRATEGY_ARTIFACT_PREFIX = "strategy_plan"
THINKSCRIPT_OUTPUT_PREFIX = "thinkscript"


def get_strategy_artifact_path(*, ticker: str, interval: str) -> Path:
    """Return deterministic strategy artifact path for ticker/interval."""
    
    safe_interval = interval.replace("/", "_")
    return config.OUTPUTS_DIR / f"{STRATEGY_ARTIFACT_PREFIX}_{ticker.upper()}_{safe_interval}.json"


def get_thinkscript_output_path(*, ticker: str, interval: str, export_mode: str) -> Path:
    """Return deterministic ThinkScript text output path."""
    
    safe_interval = interval.replace("/", "_")
    return (
        config.OUTPUTS_DIR / 
        f"{THINKSCRIPT_OUTPUT_PREFIX}_{ticker.upper()}_{safe_interval}_{export_mode}.txt"
    )


def load_artifact_payload(*, ticker: str, interval: str) -> dict[str, object]:
    """Load and validate strategy artifact payload.
    
    Raises:
        FileNotFoundError: If artifact file does not exist.
        ValueError: If artifact format is invalid.
    """
    
    artifact_path = get_strategy_artifact_path(ticker=ticker, interval=interval)
    
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Strategy artifact not found: {artifact_path}. "
            "Run build-strategy before export-thinkscript."
        )
    
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid strategy artifact format in {artifact_path}")
    
    return payload


def load_artifact_payload_optional(*, ticker: str, interval: str) -> dict[str, object] | None:
    """Load strategy artifact payload if available, return None if not found.
    
    Raises:
        ValueError: If artifact format is invalid (but file exists).
    """
    
    artifact_path = get_strategy_artifact_path(ticker=ticker, interval=interval)
    if not artifact_path.exists():
        return None
    
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid strategy artifact format in {artifact_path}")
    
    return payload
