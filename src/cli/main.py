"""
Command-line interface for the stock-analysis toolkit.

The CLI is intentionally small and easy to extend. It delegates the heavy lifting
to the underlying modules in :pymod:`src.data` and :pymod:`src.analysis`.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import pandas as pd

try:
    # Package execution: `python -m src.cli.main`
    from .. import analysis, data
    from ..analysis import thinkscript_artifact
except ImportError:
    # Direct script execution: `python src/cli/main.py`
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src import analysis, data
    from src.analysis import thinkscript_artifact

__all__ = ["main"]

# CLI configuration constants
FETCH_EXPORT_DIR = Path("downloads")
FETCH_DELAY_MIN_SECONDS = 0.3
FETCH_DELAY_MAX_SECONDS = 0.5


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
    analyze.add_argument("strategy", help="Strategy name as found in the strategy CSV")
    analyze.add_argument("ticker", help="Ticker to join with the strategy data")
    analyze.add_argument("--file", required=True, type=Path, help="Path to the strategy CSV file")
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
        expected_category = analysis.map_interval_to_category(args.interval)
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

    if args.command == "fetch":
        if args.save:
            data.market_repository.clear_saved_fetch_snapshots(output_dir=FETCH_EXPORT_DIR)

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
            display_df = data.session_cache.resolve_fetch_dataframe(
                market_data_access=data.market_data_access,
                ticker=ticker,
                interval=args.interval,
                fallback_df=fetched_df,
            )

            if args.save:
                saved_path = data.market_repository.save_market_snapshot_csv(
                    df=display_df,
                    ticker=ticker,
                    output_dir=FETCH_EXPORT_DIR,
                )
                print(f"Saved fetched data to {saved_path}")

            _print_fetch_output(df=display_df, args=args, ticker=ticker)

            if index < len(args.tickers) - 1:
                time.sleep(random.uniform(FETCH_DELAY_MIN_SECONDS, FETCH_DELAY_MAX_SECONDS))

    elif args.command == "analyze":
        try:
            strategy_df = data.load_strategy_from_file(args.file)
            market_df = data.session_cache.resolve_analyze_market_df(
                market_module=data.market,
                market_data_access=data.market_data_access,
                ticker=args.ticker,
                interval=args.interval,
            )
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        try:
            strategy_payload = thinkscript_artifact.load_artifact_payload_optional(
                ticker=args.ticker,
                interval=args.interval,
            )
            metrics, refinement = analysis.run_analyze_workflow(
                strategy_name=args.strategy,
                ticker=args.ticker,
                interval=args.interval,
                strategy_df=strategy_df,
                market_df=market_df,
                strategy_payload=strategy_payload,
            )
            for name, value in metrics.items():
                print(f"{name}: {value:.4f}")
            print(
                f"Refinement scaffold: status={refinement.status}, "
                f"suggestions={refinement.suggestion_count}, interval={refinement.interval}"
            )
            print(refinement.summary)
            for suggestion in refinement.suggestions:
                print(f"- {suggestion}")
        except (OSError, ValueError) as exc:
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

        try:
            result = analysis.run_build_strategy_workflow(
                ticker=args.ticker,
                interval=args.interval,
                category=args.category,
                market_data_access=data.market_data_access,
            )
        except ValueError as exc:
            print(f"Failed to build strategy: {exc}", file=sys.stderr)
            sys.exit(1)

        artifact_path = thinkscript_artifact.save_strategy_artifact(result)
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
