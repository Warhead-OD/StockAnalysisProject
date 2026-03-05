"""Unit tests for strategy CSV loader.

These tests cover normal loading and error handling.
"""

import pandas as pd
from pathlib import Path
import shutil

import pytest

from src.data import strategy

# Path to the sample CSV provided by the user
SAMPLE_CSV = Path("StrategyReports_SPY_3426.csv")


def test_load_csv_success(tmp_path):
    # Use a copy to avoid modifying the original
    temp_file = tmp_path / "sample.csv"
    shutil.copy2(SAMPLE_CSV, temp_file)

    df = strategy.load_csv(temp_file)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "date" in df.columns
    assert "return" in df.columns


def test_load_csv_missing_file():
    with pytest.raises(FileNotFoundError):
        strategy.load_csv(Path("nonexistent.csv"))

