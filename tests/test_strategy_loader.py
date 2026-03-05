"""Unit tests for strategy CSV loader.

These tests cover normal loading and error handling.
"""

import pandas as pd
from pathlib import Path
import shutil

import pytest

from src.data import strategy
from src.data import market

# Path to the sample CSV provided by the user
SAMPLE_CSV = Path("tests/StrategyReports_SPY_3426.csv")


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


def test_fetch_yfinance_raises_on_non_dataframe(monkeypatch):
    import yfinance as yf

    monkeypatch.setattr(yf, "download", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="Failed to download market data"):
        market.fetch_yfinance("SPY", "2026-01-01", "2026-01-31")


def test_fetch_yfinance_normalizes_output(monkeypatch):
    import yfinance as yf

    date_index = pd.date_range("2026-01-01", periods=2, freq="D", name="Date")
    downloaded = pd.DataFrame({"Adj Close": [100.0, 101.0]}, index=date_index)

    monkeypatch.setattr(yf, "download", lambda *_args, **_kwargs: downloaded)

    df = market.fetch_yfinance("SPY", "2026-01-01", "2026-01-31")

    assert isinstance(df, pd.DataFrame)
    assert "Date" in df.columns
    assert "adj_close" in df.columns
