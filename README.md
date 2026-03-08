# AI Stock Analysis

A lightweight Python toolkit for:
- Loading strategy-report CSV files
- Fetching market data from yfinance
- Running simple strategy metrics from the CLI

## Installation

```bash
pip install -e .
```

## CLI Usage

Run as a module:

```bash
python -m src.cli.main --help
```

### `load`

```bash
python -m src.cli.main load --file tests/StrategyReports_SPY_3426.csv
```

### `fetch`

Downloads market data from yfinance. You can choose either:
- Date-range mode with `--start` and optional `--end`
- Recent-window mode with `--period`

`--period` is mutually exclusive with `--start/--end`.

#### Examples

Daily bars in a date range:

```bash
python -m src.cli.main fetch AAPL --start 2025-01-01 --end 2025-03-01
```

Intraday bars in a recent period:

```bash
python -m src.cli.main fetch SPY --period 5d --interval 5m
```

Include extended hours and corporate actions:

```bash
python -m src.cli.main fetch MSFT --period 1mo --interval 30m --prepost --actions
```

Save fetched data to a CSV snapshot for later strategy development:

```bash
python -m src.cli.main fetch AAPL --period 1mo --interval 1d --save
```

Fetch multiple tickers with shared settings:

```bash
python -m src.cli.main fetch AAPL MSFT NVDA --period 5d --interval 30m --save
```

#### Fetch Flags

- `tickers` (positional): One or more ticker symbols, for example `AAPL MSFT`
- `--start YYYY-MM-DD`: Start date (date-range mode)
- `--end YYYY-MM-DD`: End date, requires `--start`
- `--period`: Recent window from yfinance
  - Supported: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`
- `--interval`: Candle/bar interval
  - Supported: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo`
- `--auto-adjust`: Adjust prices for splits/dividends
- `--prepost`: Include pre/post-market bars (when available)
- `--actions`: Include dividends and split columns
- `--limit N`: Print only the first `N` rows to console
- `--all`: Print all rows to console
- `--save`: Save fetched data to `downloads/latest_market_data_<TICKER>.csv`

Output behavior:
- If neither `--limit` nor `--all` is provided, the CLI prints the first 3 and last 3 rows.
- Fetch requests are run sequentially, and each ticker request starts after the previous one completes with a random 300-500ms delay.
- If `--save` is provided, previous `latest_market_data_*.csv` snapshots are deleted once at the start of the run, then one CSV is saved per fetched ticker.

Note: `10m` is not currently a native yfinance interval.

### `analyze`

```bash
python -m src.cli.main analyze demo-strategy SPY
```

## Data Normalization

Fetched market data is normalized to lowercase columns where possible:
- `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`

This makes merges and metric pipelines more predictable.

## Storage Layout

Fetched market datasets are stored in efficient machine-readable formats for downstream strategy building:
- Canonical dataset files: `downloads/market/latest_market_<TICKER>_<INTERVAL>.parquet`
- Metadata sidecar files: `downloads/meta/latest_market_<TICKER>_<INTERVAL>.json`

If `--save` is used, user-facing CSV snapshots are still generated in `downloads/` for quick manual inspection.
