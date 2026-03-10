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
FETCH_DELAY_MIN_SECONDS = 0.3
FETCH_DELAY_MAX_SECONDS = 0.5
STRATEGY_OUTPUT_PREFIX = "strategy_plan"
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
        strategy_df = data.strategy.get_loaded()
        market_df = data.market.get_loaded()
        merged = strategy_df.merge(market_df, on="date")
        metrics = analysis.metrics.compute_all(merged)
        for name, value in metrics.items():
            print(f"{name}: {value:.4f}")

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

    else:
        print("Unknown command", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
