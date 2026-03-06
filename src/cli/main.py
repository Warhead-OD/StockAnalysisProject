"""
Command-line interface for the stock-analysis toolkit.

The CLI is intentionally small and easy to extend. It delegates the heavy lifting
to the underlying modules in :pymod:`src.data` and :pymod:`src.analysis`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    # Package execution: `python -m src.cli.main`
    from .. import analysis, data
except ImportError:
    # Direct script execution: `python src/cli/main.py`
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src import analysis, data

__all__ = ["main"]


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
    fetch.add_argument("ticker", help="Ticker symbol (e.g., AAPL)")
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

    # analyze
    analyze = sub.add_parser("analyze", help="Run metrics on a loaded strategy and market data")
    analyze.add_argument("strategy", help="Strategy name as found in the loaded CSV")
    analyze.add_argument("ticker", help="Ticker to join with the strategy data")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        if args.period and (args.start or args.end):
            parser.error("--period cannot be combined with --start/--end")
        if args.end and not args.start:
            parser.error("--end requires --start")
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be a positive integer")

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
        df = data.market.fetch_yfinance(
            ticker=args.ticker,
            start=args.start,
            end=args.end,
            period=args.period,
            interval=args.interval,
            auto_adjust=args.auto_adjust,
            prepost=args.prepost,
            actions=args.actions,
        )
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

    elif args.command == "analyze":
        strategy_df = data.strategy.get_loaded()
        market_df = data.market.get_loaded()
        merged = strategy_df.merge(market_df, on="date")
        metrics = analysis.metrics.compute_all(merged)
        for name, value in metrics.items():
            print(f"{name}: {value:.4f}")

    else:
        print("Unknown command", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
