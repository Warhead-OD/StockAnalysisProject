"""Session/cache helpers for strategy and market data workflows.

These APIs are CLI-independent and can be reused by other interfaces.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FETCH_EXPORT_DIR = Path("downloads")
STRATEGY_IMPORT_DIR = FETCH_EXPORT_DIR / "strategy_imports"
STRATEGY_REPORT_CACHE_FILE = "latest_loaded_strategy_report.csv"


def strategy_report_cache_path(
    *,
    import_dir: Path | None = None,
    cache_file: str = STRATEGY_REPORT_CACHE_FILE,
) -> Path:
    """Return the strategy-report cache path for cross-session analyze fallbacks."""

    target_dir = import_dir or STRATEGY_IMPORT_DIR
    return target_dir / cache_file


def save_strategy_report_cache(
    df: pd.DataFrame,
    *,
    import_dir: Path | None = None,
    cache_file: str = STRATEGY_REPORT_CACHE_FILE,
) -> Path:
    """Persist the latest loaded strategy report for future analyze runs."""

    cache_path = strategy_report_cache_path(import_dir=import_dir, cache_file=cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return cache_path


def load_strategy_report_cache(
    *,
    import_dir: Path | None = None,
    cache_file: str = STRATEGY_REPORT_CACHE_FILE,
) -> pd.DataFrame | None:
    """Load strategy-report cache if it exists, otherwise return None."""

    cache_path = strategy_report_cache_path(import_dir=import_dir, cache_file=cache_file)
    if not cache_path.exists():
        return None
    return pd.read_csv(cache_path)


def resolve_analyze_strategy_df(
    *,
    strategy_module,
    import_dir: Path | None = None,
    cache_file: str = STRATEGY_REPORT_CACHE_FILE,
) -> pd.DataFrame:
    """Resolve strategy data for analyze from memory first, then persisted cache."""

    try:
        return strategy_module.get_loaded()
    except RuntimeError:
        cached = load_strategy_report_cache(import_dir=import_dir, cache_file=cache_file)
        if cached is not None:
            return cached
        raise RuntimeError(
            "No strategy has been loaded yet. Run `load --file <strategy_csv>` first "
            "(or ensure a cached strategy report exists)."
        )


def resolve_analyze_market_df(
    *,
    market_module,
    market_data_access,
    ticker: str,
    interval: str,
) -> pd.DataFrame:
    """Resolve market data for analyze from memory first, then persisted artifacts."""

    try:
        return market_module.get_loaded()
    except RuntimeError:
        if market_data_access.has_dataset(ticker=ticker, interval=interval):
            return market_data_access.load_dataset(ticker=ticker, interval=interval)
        raise RuntimeError(
            "No market data has been loaded yet. Run `fetch` first for this ticker/interval."
        )


def resolve_fetch_dataframe(
    *,
    market_data_access,
    ticker: str,
    interval: str,
    fallback_df: pd.DataFrame,
) -> pd.DataFrame:
    """Use persisted parquet artifacts for display/export when available."""

    if market_data_access.has_dataset(ticker=ticker, interval=interval):
        return market_data_access.load_dataset(ticker=ticker, interval=interval)
    return fallback_df
