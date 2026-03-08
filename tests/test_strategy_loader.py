"""
Unit tests for strategy CSV loader.

These tests cover normal loading and error handling.
"""

import pandas as pd
from pathlib import Path
import shutil

import pytest

import src.data as data_module
from src.data import strategy
from src.data import market

# Path to the sample CSV provided by the user
SAMPLE_CSV = Path("tests/StrategyReports_SPY_3426.csv")


def test_load_csv_success(tmp_path):
    """
    Test successful loading of a strategy CSV file.
    Verifies that the DataFrame is not empty and contains expected columns.
    """

    # Use a copy to avoid modifying the original
    temp_file = tmp_path / "sample.csv"
    shutil.copy2(SAMPLE_CSV, temp_file)

    df = strategy.load_csv(temp_file)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "date" in df.columns
    assert "return" in df.columns


def test_load_csv_missing_file():
    """
    Test loading a missing CSV file raises FileNotFoundError.
    """

    with pytest.raises(FileNotFoundError):
        strategy.load_csv(Path("nonexistent.csv"))


def test_fetch_yfinance_raises_on_non_dataframe(monkeypatch):
    """
    Test that fetch_yfinance raises RuntimeError when yfinance returns None.
    """

    import yfinance as yf

    monkeypatch.setattr(yf, "download", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        data_module,
        "save_market_dataset",
        lambda *_args, **_kwargs: (Path("downloads/market/mock.parquet"), Path("downloads/meta/mock.json")),
    )

    with pytest.raises(RuntimeError, match="Failed to download market data"):
        market.fetch_yfinance("SPY", "2026-01-01", "2026-01-31")


def test_fetch_yfinance_normalizes_output(monkeypatch):
    """
    Test that fetch_yfinance normalizes output DataFrame columns.
    """

    import yfinance as yf

    date_index = pd.date_range("2026-01-01", periods=2, freq="D", name="Date")
    downloaded = pd.DataFrame({"Adj Close": [100.0, 101.0]}, index=date_index)

    monkeypatch.setattr(yf, "download", lambda *_args, **_kwargs: downloaded)
    monkeypatch.setattr(
        data_module,
        "save_market_dataset",
        lambda *_args, **_kwargs: (Path("downloads/market/mock.parquet"), Path("downloads/meta/mock.json")),
    )

    df = market.fetch_yfinance("SPY", "2026-01-01", "2026-01-31")

    assert isinstance(df, pd.DataFrame)
    assert "date" in df.columns
    assert "adj_close" in df.columns


def test_fetch_yfinance_period_and_interval_are_forwarded(monkeypatch):
    """Test that period/interval and optional flags are passed to yfinance."""

    import yfinance as yf

    observed: dict[str, object] = {}
    date_index = pd.date_range("2026-01-01", periods=1, freq="D", name="Date")
    downloaded = pd.DataFrame({"Adj Close": [100.0]}, index=date_index)

    def fake_download(**kwargs):
        observed.update(kwargs)
        return downloaded

    monkeypatch.setattr(yf, "download", fake_download)
    monkeypatch.setattr(
        data_module,
        "save_market_dataset",
        lambda *_args, **_kwargs: (Path("downloads/market/mock.parquet"), Path("downloads/meta/mock.json")),
    )

    market.fetch_yfinance(
        "SPY",
        period="5d",
        interval="30m",
        auto_adjust=True,
        prepost=True,
        actions=True,
    )

    assert observed["tickers"] == "SPY"
    assert observed["period"] == "5d"
    assert observed["interval"] == "30m"
    assert observed["auto_adjust"] is True
    assert observed["prepost"] is True
    assert observed["actions"] is True


def test_fetch_yfinance_rejects_invalid_fetch_window() -> None:
    """Test validation errors for invalid start/end/period combinations."""

    with pytest.raises(ValueError, match="cannot be combined"):
        market.fetch_yfinance("SPY", start="2026-01-01", period="1mo")

    with pytest.raises(ValueError, match="requires --start"):
        market.fetch_yfinance("SPY", end="2026-01-31")


def test_fetch_yfinance_rejects_unsupported_interval() -> None:
    """Test unsupported yfinance interval raises a helpful ValueError."""

    with pytest.raises(ValueError, match="Unsupported interval"):
        market.fetch_yfinance("SPY", interval="10m")


def test_fetch_yfinance_builds_metadata_for_persistence(monkeypatch):
    """Test that fetch builds metadata and sends both frame and metadata to persistence layer."""

    import yfinance as yf

    date_index = pd.date_range("2026-01-01", periods=3, freq="D", name="Date")
    downloaded = pd.DataFrame({"Adj Close": [100.0, 101.0, 102.0]}, index=date_index)
    observed: dict[str, object] = {}

    def fake_save(df, metadata):
        observed["df"] = df
        observed["metadata"] = metadata
        return Path("downloads/market/mock.parquet"), Path("downloads/meta/mock.json")

    monkeypatch.setattr(yf, "download", lambda *_args, **_kwargs: downloaded)
    monkeypatch.setattr(data_module, "save_market_dataset", fake_save)

    df = market.fetch_yfinance("SPY", period="5d", interval="1d")

    metadata = observed["metadata"]
    assert observed["df"].equals(df)
    assert metadata.ticker == "SPY"
    assert metadata.interval == "1d"
    assert metadata.period == "5d"
    assert metadata.row_count == 3
