"""Command‑line interface for the stock‑analysis toolkit.

The CLI is intentionally small and easy to extend. It delegates the heavy lifting
to the underlying modules in :pymod:`src.data` and :pymod:`src.analysis`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import data
from . import analysis

__all__ = ["main"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock strategy analysis toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    # load strategy
    load = sub.add_parser("load", help="Load a strategy report CSV")
    load.add_argument("--file", required=True, type=Path, help="Path to the strategy CSV file")

    # fetch market data
    fetch = sub.add_parser("fetch", help="Download historical OHLC data from yfinance")
    fetch.add_argument("ticker", help="Ticker symbol (e.g., AAPL)")
    fetch.add_argument("--start", help="Start date YYYY-MM-DD")
    fetch.add_argument("--end", help="End date YYYY-MM-DD")

    # analyze
    analyze = sub.add_parser("analyze", help="Run metrics on a loaded strategy and market data")
    analyze.add_argument("strategy", help="Strategy name as found in the loaded CSV")
    analyze.add_argument("ticker", help="Ticker to join with the strategy data")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.command == "load":
        strategy = data.strategy.load_csv(args.file)
        print(f"Loaded strategy with {len(strategy)} rows")
        # store strategy in a temporary location; a more complete project
        # would persist it in memory or a cache.

    elif args.command == "fetch":
        df = data.market.fetch_yfinance(args.ticker, args.start, args.end)
        print(df.head())

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
