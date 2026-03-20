"""Unit tests for reusable data session/cache helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data import session_cache


def test_save_and_load_strategy_report_cache_round_trip(tmp_path: Path) -> None:
    """Saved strategy cache should be readable from the same configured import directory."""

    strategy_df = pd.DataFrame({"date": ["2026-01-01"], "return": [0.01]})

    cache_path = session_cache.save_strategy_report_cache(strategy_df, import_dir=tmp_path)
    loaded = session_cache.load_strategy_report_cache(import_dir=tmp_path)

    assert cache_path == tmp_path / session_cache.STRATEGY_REPORT_CACHE_FILE
    assert loaded is not None
    assert loaded.equals(strategy_df)


def test_resolve_analyze_strategy_df_prefers_in_memory_loaded_data() -> None:
    """Analyze strategy resolver should return in-memory data without touching cache."""

    expected = pd.DataFrame({"date": ["2026-01-01"], "return": [0.02]})

    class _StrategyModule:
        @staticmethod
        def get_loaded() -> pd.DataFrame:
            return expected

    resolved = session_cache.resolve_analyze_strategy_df(strategy_module=_StrategyModule())

    assert resolved.equals(expected)


def test_resolve_analyze_strategy_df_falls_back_to_cache(tmp_path: Path) -> None:
    """Analyze strategy resolver should use persisted cache when in-memory data is unavailable."""

    expected = pd.DataFrame({"date": ["2026-01-01"], "return": [0.03]})
    session_cache.save_strategy_report_cache(expected, import_dir=tmp_path)

    class _StrategyModule:
        @staticmethod
        def get_loaded() -> pd.DataFrame:
            raise RuntimeError("No strategy has been loaded yet")

    resolved = session_cache.resolve_analyze_strategy_df(strategy_module=_StrategyModule(), import_dir=tmp_path)

    assert resolved.equals(expected)


def test_resolve_analyze_market_df_falls_back_to_dataset_loader() -> None:
    """Analyze market resolver should load persisted artifacts when market memory cache is empty."""

    expected = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [101.0]})

    class _MarketModule:
        @staticmethod
        def get_loaded() -> pd.DataFrame:
            raise RuntimeError("No market data has been fetched yet")

    class _MarketDataAccess:
        @staticmethod
        def has_dataset(*, ticker: str, interval: str) -> bool:
            assert ticker == "AAPL"
            assert interval == "1d"
            return True

        @staticmethod
        def load_dataset(*, ticker: str, interval: str) -> pd.DataFrame:
            assert ticker == "AAPL"
            assert interval == "1d"
            return expected

    resolved = session_cache.resolve_analyze_market_df(
        market_module=_MarketModule(),
        market_data_access=_MarketDataAccess(),
        ticker="AAPL",
        interval="1d",
    )

    assert resolved.equals(expected)


def test_resolve_fetch_dataframe_prefers_persisted_dataset_when_available() -> None:
    """Fetch resolver should use persisted parquet-backed data for display/save when present."""

    fetched_df = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})
    persisted_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [200.0, 201.0]})

    class _MarketDataAccess:
        @staticmethod
        def has_dataset(*, ticker: str, interval: str) -> bool:
            assert ticker == "AAPL"
            assert interval == "1d"
            return True

        @staticmethod
        def load_dataset(*, ticker: str, interval: str) -> pd.DataFrame:
            return persisted_df

    resolved = session_cache.resolve_fetch_dataframe(
        market_data_access=_MarketDataAccess(),
        ticker="AAPL",
        interval="1d",
        fallback_df=fetched_df,
    )

    assert resolved.equals(persisted_df)
