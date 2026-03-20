"""
Command-line interface for the stock-analysis toolkit.

The CLI is intentionally small and easy to extend. It delegates the heavy lifting
to the underlying modules in :pymod:`src.data` and :pymod:`src.analysis`.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd

try:
    # Package execution: `python -m src.cli.main`
    from .. import analysis, config, data
except ImportError:
    # Direct script execution: `python src/cli/main.py`
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src import analysis, config, data

__all__ = ["main"]

FETCH_EXPORT_DIR = Path("downloads")
FETCH_EXPORT_PREFIX = "latest_market_data"
STRATEGY_IMPORT_DIR = FETCH_EXPORT_DIR / "strategy_imports"
STRATEGY_REPORT_CACHE_FILE = "latest_loaded_strategy_report.csv"
FETCH_DELAY_MIN_SECONDS = 0.3
FETCH_DELAY_MAX_SECONDS = 0.5
STRATEGY_OUTPUT_PREFIX = "strategy_plan"
THINKSCRIPT_OUTPUT_PREFIX = "thinkscript"
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
DAILY_INTERVALS = {"1d", "5d"}
LONG_TERM_INTERVALS = {"1wk", "1mo", "3mo"}


def _clear_saved_fetch_data(output_dir: Path | None = None) -> None:
    """Remove previous saved fetch snapshots before a new save run."""

    target_dir = output_dir or FETCH_EXPORT_DIR
    if not target_dir.exists():
        return

    for existing in target_dir.glob(f"{FETCH_EXPORT_PREFIX}_*.csv"):
        if existing.is_file():
            existing.unlink()


def _save_fetched_data(df: pd.DataFrame, ticker: str, output_dir: Path | None = None) -> Path:
    """Persist fetched market data for a single ticker."""

    target_dir = output_dir or FETCH_EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = re.sub(r"[^A-Za-z0-9._-]", "_", ticker.strip().upper())
    output_path = target_dir / f"{FETCH_EXPORT_PREFIX}_{safe_ticker}.csv"
    df.to_csv(output_path, index=False)
    return output_path


def _strategy_report_cache_path() -> Path:
    """Return path used to persist the latest loaded strategy report for analyze fallback."""

    return STRATEGY_IMPORT_DIR / STRATEGY_REPORT_CACHE_FILE


def _save_strategy_report_cache(df: pd.DataFrame) -> Path:
    """Persist latest loaded strategy report so analyze can run across separate CLI invocations."""

    cache_path = _strategy_report_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return cache_path


def _load_strategy_report_cache() -> pd.DataFrame | None:
    """Load persisted strategy report cache if present."""

    cache_path = _strategy_report_cache_path()
    if not cache_path.exists():
        return None
    return pd.read_csv(cache_path)


def _resolve_analyze_strategy_df() -> pd.DataFrame:
    """Return loaded strategy report, falling back to persisted cache between CLI commands."""

    try:
        return data.strategy.get_loaded()
    except RuntimeError:
        cached = _load_strategy_report_cache()
        if cached is not None:
            return cached
        raise RuntimeError(
            "No strategy has been loaded yet. Run `load --file <strategy_csv>` first "
            "(or ensure a cached strategy report exists)."
        )


def _resolve_analyze_market_df(*, ticker: str, interval: str) -> pd.DataFrame:
    """Return loaded market data, falling back to persisted market artifacts between CLI commands."""

    try:
        return data.market.get_loaded()
    except RuntimeError:
        if data.market_data_access.has_dataset(ticker=ticker, interval=interval):
            return data.market_data_access.load_dataset(ticker=ticker, interval=interval)
        raise RuntimeError(
            "No market data has been loaded yet. Run `fetch` first for this ticker/interval."
        )


def _normalize_analyze_date_columns(
    *,
    strategy_df: pd.DataFrame,
    market_df: pd.DataFrame,
    interval: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize strategy/market date keys so merge uses compatible types.

    Daily and higher-timeframe intervals merge on date-only keys.
    Intraday intervals merge on second-resolution timestamp keys.
    """

    if "date" not in strategy_df.columns:
        raise ValueError("Strategy dataframe is missing required 'date' column")
    if "date" not in market_df.columns:
        raise ValueError("Market dataframe is missing required 'date' column")

    strategy = strategy_df.copy()
    market = market_df.copy()
    strategy_dates = pd.to_datetime(strategy["date"], errors="coerce")
    market_dates = pd.to_datetime(market["date"], errors="coerce")

    if strategy_dates.isna().any():
        raise ValueError("Strategy dataframe contains invalid date values")
    if market_dates.isna().any():
        raise ValueError("Market dataframe contains invalid date values")

    if interval in DAILY_INTERVALS or interval in LONG_TERM_INTERVALS:
        strategy["date"] = strategy_dates.dt.strftime("%Y-%m-%d")
        market["date"] = market_dates.dt.strftime("%Y-%m-%d")
    else:
        strategy["date"] = strategy_dates.dt.strftime("%Y-%m-%d %H:%M:%S")
        market["date"] = market_dates.dt.strftime("%Y-%m-%d %H:%M:%S")

    return strategy, market


def _print_fetch_output(df: pd.DataFrame, args: argparse.Namespace, ticker: str) -> None:
    """Print fetch results according to the selected output controls."""

    print(f"Ticker: {ticker.upper()}")
    if args.all:
        print(df)
    elif args.limit is not None:
        print(df.head(args.limit))
    elif len(df) <= 6:
        print(df)
    else:
        print(f"Fetched {len(df)} rows. Showing first 3 and last 3 rows.")
        print(df.head(3))
        print("...")
        print(df.tail(3))


def _resolve_fetch_dataframe(
    *,
    ticker: str,
    interval: str,
    fallback_df: pd.DataFrame,
) -> pd.DataFrame:
    """Use persisted parquet artifacts for CLI display when available."""

    if data.market_data_access.has_dataset(ticker=ticker, interval=interval):
        return data.market_data_access.load_dataset(ticker=ticker, interval=interval)
    return fallback_df


def _interval_category(interval: str) -> str:
    """Return strategy category implied by a market-data interval."""

    if interval in INTRADAY_INTERVALS:
        return "intraday"
    if interval in DAILY_INTERVALS:
        return "daily"
    if interval in LONG_TERM_INTERVALS:
        return "long-term"
    raise ValueError(f"No strategy category mapping exists for interval '{interval}'")


def _save_strategy_artifact(
    result: analysis.StrategyBuildResult,
    output_dir: Path | None = None,
) -> Path:
    """Persist generated strategy result as a deterministic JSON artifact."""

    target_dir = output_dir or config.OUTPUTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_interval = result.interval.replace("/", "_")
    artifact_path = target_dir / f"{STRATEGY_OUTPUT_PREFIX}_{result.ticker}_{safe_interval}.json"
    artifact_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return artifact_path


def _strategy_artifact_path(*, ticker: str, interval: str) -> Path:
    """Return deterministic strategy artifact path for ticker/interval."""

    safe_interval = interval.replace("/", "_")
    return config.OUTPUTS_DIR / f"{STRATEGY_OUTPUT_PREFIX}_{ticker.upper()}_{safe_interval}.json"


def _thinkscript_output_path(*, ticker: str, interval: str, export_mode: str) -> Path:
    """Return deterministic ThinkScript text output path."""

    safe_interval = interval.replace("/", "_")
    return config.OUTPUTS_DIR / f"{THINKSCRIPT_OUTPUT_PREFIX}_{ticker.upper()}_{safe_interval}_{export_mode}.txt"


def _load_strategy_artifact_payload(*, ticker: str, interval: str) -> dict[str, object] | None:
    """Load strategy artifact payload for refinement workflows when available."""

    strategy_path = _strategy_artifact_path(ticker=ticker, interval=interval)
    if not strategy_path.exists():
        return None

    payload = json.loads(strategy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid strategy artifact format in {strategy_path}")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments for the stock analysis CLI.

    Args:
        argv (list[str] | None): List of command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments namespace.
    """

    parser = argparse.ArgumentParser(description="Stock strategy analysis toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    # load strategy
    load = sub.add_parser("load", help="Load a strategy report CSV")
    load.add_argument("--file", required=True, type=Path, help="Path to the strategy CSV file")

    # fetch market data
    fetch = sub.add_parser("fetch", help="Download historical OHLC data from yfinance")
    fetch.add_argument("tickers", nargs="+", help="One or more ticker symbols (e.g., AAPL MSFT)")
    fetch.add_argument("--start", help="Start date YYYY-MM-DD (date-range mode)")
    fetch.add_argument("--end", help="End date YYYY-MM-DD (requires --start)")
    fetch.add_argument(
        "--period",
        choices=data.market.SUPPORTED_PERIODS,
        help="Recent lookback window, e.g. 1d, 5d, 1mo, ytd (mutually exclusive with --start/--end)",
    )
    fetch.add_argument(
        "--interval",
        default="1d",
        choices=data.market.SUPPORTED_INTERVALS,
        help="Sampling interval, e.g. 1m, 5m, 30m, 1d (default: 1d)",
    )
    fetch.add_argument(
        "--auto-adjust",
        action="store_true",
        help="Adjust OHLC prices for splits/dividends",
    )
    fetch.add_argument(
        "--prepost",
        action="store_true",
        help="Include pre and post market data when available",
    )
    fetch.add_argument(
        "--actions",
        action="store_true",
        help="Include dividends and stock split columns",
    )
    output_scope = fetch.add_mutually_exclusive_group()
    output_scope.add_argument(
        "--limit",
        type=int,
        help="Print only the first N rows",
    )
    output_scope.add_argument(
        "--all",
        action="store_true",
        help="Print all fetched rows",
    )
    fetch.add_argument(
        "--save",
        action="store_true",
        help="Save fetched data to downloads/latest_market_data_<TICKER>.csv and replace prior saved fetch file",
    )

    # analyze
    analyze = sub.add_parser("analyze", help="Run metrics on a loaded strategy and market data")
    analyze.add_argument("strategy", help="Strategy name as found in the loaded CSV")
    analyze.add_argument("ticker", help="Ticker to join with the strategy data")
    analyze.add_argument(
        "--interval",
        default="1d",
        choices=data.market.SUPPORTED_INTERVALS,
        help="Interval used to resolve a generated strategy artifact for refinement (default: 1d)",
    )

    # build strategy (scaffold)
    build_strategy = sub.add_parser(
        "build-strategy",
        help="Build a strategy from previously fetched market data (scaffold)",
    )
    build_strategy.add_argument("ticker", help="Single ticker symbol to build strategy for")
    build_strategy.add_argument(
        "--interval",
        required=True,
        choices=data.market.SUPPORTED_INTERVALS,
        help="Target strategy interval (e.g., 5m, 1h, 1d)",
    )
    build_strategy.add_argument(
        "--category",
        choices=["intraday", "daily", "long-term"],
        help="Optional strategy category label for simplified workflow",
    )

    # export thinkscript (scaffold)
    export_thinkscript = sub.add_parser(
        "export-thinkscript",
        help="Export ThinkScript from a generated strategy artifact",
    )
    export_thinkscript.add_argument("ticker", help="Ticker symbol for the strategy artifact")
    export_thinkscript.add_argument(
        "--interval",
        required=True,
        choices=data.market.SUPPORTED_INTERVALS,
        help="Interval used by the generated strategy artifact",
    )
    export_thinkscript.add_argument(
        "--mode",
        choices=["strategy", "study"],
        default="strategy",
        help="ThinkScript export mode (default: strategy)",
    )
    export_thinkscript.add_argument(
        "--disable-orders",
        action="store_true",
        help="Disable order lines in the exported script scaffold",
    )

    args = parser.parse_args(argv)

    if args.command == "fetch":
        if args.period and (args.start or args.end):
            parser.error("--period cannot be combined with --start/--end")
        if args.end and not args.start:
            parser.error("--end requires --start")
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be a positive integer")
    if args.command == "build-strategy" and args.category:
        expected_category = _interval_category(args.interval)
        if args.category != expected_category:
            parser.error(
                f"--category {args.category} does not match interval {args.interval} "
                f"(expected {expected_category})"
            )

    return args


def main(argv: list[str] | None = None) -> None:
    """
    Main entry point for the CLI. Handles command routing and delegates to appropriate modules.

    Args:
        argv (list[str] | None): List of command-line arguments.
    """

    args = _parse_args(argv)

    if args.command == "load":
        strategy = data.strategy.load_csv(args.file)
        _save_strategy_report_cache(strategy)
        print(f"Loaded strategy with {len(strategy)} rows")
        # store strategy in a temporary location; a more complete project
        # would persist it in memory or a cache.

    elif args.command == "fetch":
        if args.save:
            _clear_saved_fetch_data()

        for index, ticker in enumerate(args.tickers):
            fetched_df = data.market.fetch_yfinance(
                ticker=ticker,
                start=args.start,
                end=args.end,
                period=args.period,
                interval=args.interval,
                auto_adjust=args.auto_adjust,
                prepost=args.prepost,
                actions=args.actions,
            )
            display_df = _resolve_fetch_dataframe(
                ticker=ticker,
                interval=args.interval,
                fallback_df=fetched_df,
            )

            if args.save:
                saved_path = _save_fetched_data(df=display_df, ticker=ticker)
                print(f"Saved fetched data to {saved_path}")

            _print_fetch_output(df=display_df, args=args, ticker=ticker)

            if index < len(args.tickers) - 1:
                time.sleep(random.uniform(FETCH_DELAY_MIN_SECONDS, FETCH_DELAY_MAX_SECONDS))

    elif args.command == "analyze":
        try:
            strategy_df = _resolve_analyze_strategy_df()
            market_df = _resolve_analyze_market_df(ticker=args.ticker, interval=args.interval)
            strategy_df, market_df = _normalize_analyze_date_columns(
                strategy_df=strategy_df,
                market_df=market_df,
                interval=args.interval,
            )
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        merged = strategy_df.merge(market_df, on="date")
        metrics = analysis.metrics.compute_all(merged)
        for name, value in metrics.items():
            print(f"{name}: {value:.4f}")

        try:
            strategy_payload = _load_strategy_artifact_payload(ticker=args.ticker, interval=args.interval)
            refinement_request = analysis.StrategyRefinementRequest(
                strategy_name=args.strategy,
                ticker=args.ticker,
                interval=args.interval,
            )
            refinement = analysis.refine_strategy_from_report_scaffold(
                request=refinement_request,
                strategy_report_df=strategy_df,
                market_df=market_df,
                strategy_payload=strategy_payload,
            )
            print(
                f"Refinement scaffold: status={refinement.status}, "
                f"suggestions={refinement.suggestion_count}, interval={refinement.interval}"
            )
            print(refinement.summary)
            for suggestion in refinement.suggestions:
                print(f"- {suggestion}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Skipped refinement scaffold: {exc}", file=sys.stderr)

    elif args.command == "build-strategy":
        if not data.market_data_access.has_dataset(ticker=args.ticker, interval=args.interval):
            print(
                "Cannot run build-strategy: required fetched market data was not found. "
                "Run fetch first for this ticker and interval.",
                file=sys.stderr,
            )
            sys.exit(1)

        metadata = data.market_data_access.load_metadata(ticker=args.ticker, interval=args.interval)
        dataset = data.market_data_access.load_dataset(ticker=args.ticker, interval=args.interval)
        category = args.category or _interval_category(args.interval)

        try:
            build_request = analysis.StrategyBuildRequest(
                ticker=args.ticker,
                interval=args.interval,
                category=category,
            )
            result = analysis.trend_following_builder.build(build_request, dataset)
        except ValueError as exc:
            print(f"Failed to build strategy: {exc}", file=sys.stderr)
            sys.exit(1)

        artifact_path = _save_strategy_artifact(result)
        print(
            f"Built strategy {result.strategy_id} for {metadata.ticker} "
            f"({metadata.interval}, rows={result.data_row_count}, status={result.status})."
        )
        print(
            f"Saved strategy artifact to {artifact_path}"
        )

    elif args.command == "export-thinkscript":
        try:
            result = analysis.export_thinkscript(
                ticker=args.ticker,
                interval=args.interval,
                export_mode=args.mode,
                include_orders=not args.disable_orders,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Failed to export ThinkScript: {exc}", file=sys.stderr)
            sys.exit(1)

        print(
            f"Exported ThinkScript for {result.ticker} "
            f"({result.interval}, mode={result.export_mode}, status={result.status})."
        )
        print(f"Saved ThinkScript artifact to {result.output_path}")

    else:
        print("Unknown command", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
