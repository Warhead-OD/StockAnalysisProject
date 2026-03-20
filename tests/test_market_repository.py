"""Unit tests for market repository persistence helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data import market_repository


def test_clear_saved_fetch_snapshots_removes_matching_csv_files(tmp_path: Path) -> None:
    """Snapshot cleanup should remove only matching latest_market_data CSV files."""

    removable = tmp_path / "latest_market_data_AAPL.csv"
    keep_other = tmp_path / "other_file.csv"
    removable.write_text("date,adj_close\n2026-01-01,100\n", encoding="utf-8")
    keep_other.write_text("data\n", encoding="utf-8")

    market_repository.clear_saved_fetch_snapshots(output_dir=tmp_path)

    assert not removable.exists()
    assert keep_other.exists()


def test_save_market_snapshot_csv_writes_sanitized_ticker_filename(tmp_path: Path) -> None:
    """CSV snapshot save should use deterministic safe uppercase ticker naming."""

    df = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    output_path = market_repository.save_market_snapshot_csv(
        df,
        ticker="brk/b",
        output_dir=tmp_path,
    )

    assert output_path == tmp_path / "latest_market_data_BRK_B.csv"
    assert output_path.exists()
