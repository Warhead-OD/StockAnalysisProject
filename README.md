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
- The CLI prefers persisted Parquet data for fetch display/export when available, and falls back to the immediate in-memory fetch result if artifacts are not yet present.

### `export-thinkscript`

Converts a generated strategy artifact into a ThinkScript script file ready for import into Thinkorswim.

Requires a strategy artifact produced by `build-strategy`.

```bash
python -m src.cli.main export-thinkscript AAPL --interval 1d
```

Export as a study (no order execution blocks):

```bash
python -m src.cli.main export-thinkscript AAPL --interval 1d --mode study
```

Suppress `AddOrder` calls even in strategy mode:

```bash
python -m src.cli.main export-thinkscript AAPL --interval 1d --disable-orders
```

Flags:

- `ticker` (positional): single ticker symbol matching an existing strategy artifact
- `--interval` (required): interval matching the strategy artifact
- `--mode`: `strategy` (default) or `study`
- `--disable-orders`: suppress `AddOrder()` calls from the output

Output artifact:

- `outputs/thinkscript_<TICKER>_<INTERVAL>_<MODE>.txt`

Generated script contents:

- Header comment block with strategy ID, ticker/interval/mode/orders flag, and generation timestamp
- `declare upper;`
- Six `input` declarations wired to strategy parameters (fast/slow MA windows, breakout lookback, ATR window, stop and take-profit ATR multipliers)
- `def` blocks for `fastMA`, `slowMA`, `atr`, `swingHigh`, `trendUp`, `breakoutEntry`, `entrySignal`, `exitSignal`
- `plot BuyArrow` / `plot SellArrow` with arrow painting strategies
- `plot FastMALine` / `plot SlowMALine` overlay plots
- `AddOrder(BUY_TO_OPEN, ...)` / `AddOrder(SELL_TO_CLOSE, ...)` — present only when `mode=strategy` and orders are not disabled

### `analyze`

```bash
python -m src.cli.main analyze demo-strategy SPY --file tests/StrategyReports_SPY_3426.csv
```

Run `analyze` with an explicit interval when you want artifact-aware refinement suggestions:

```bash
python -m src.cli.main analyze demo-strategy SPY --file tests/StrategyReports_SPY_3426.csv --interval 1d
```

Current behavior:

- Loads strategy report data from `--file` and market data from persisted market artifacts.
- Merges on `date` and prints baseline metrics (`daily_mean_return`, `annualized_return`, `annualized_volatility`, `sharpe_ratio`).
- Attempts to load a matching generated strategy artifact from:
  - `outputs/strategy_plan_<TICKER>_<INTERVAL>.json`
- Runs refinement recommendation logic and prints:
  - one refinement status line
  - one refinement summary line (row counts and artifact presence)
  - bullet recommendations tied to artifact parameters and report behavior

Analyze flags:

- `strategy` (positional): strategy name label used in refinement metadata
- `ticker` (positional): ticker symbol used for artifact resolution
- `--file` (required): path to the strategy report CSV
- `--interval` (optional, default `1d`): interval for locating the strategy artifact

Refinement recommendation behavior:

- With a matching artifact: suggestions are parameter-aware (MA windows, breakout lookback, ATR multipliers) and adjusted by report win-rate/expectancy.
- Without an artifact: `analyze` still prints metrics and emits scaffold guidance to run `build-strategy` first.
- If artifact payload parsing fails: metrics still print, and refinement is skipped with a non-fatal stderr warning.

### `build-strategy`

Builds strategy artifacts from previously fetched market data for one or more tickers with a shared interval/category.

```bash
python -m src.cli.main build-strategy AAPL MSFT NVDA --interval 1d --category daily
```

Current behavior:

- Requires existing fetched artifacts for each selected ticker and interval.
- Continues processing remaining tickers if one ticker is missing data or fails.
- Prints per-ticker successes and per-ticker errors immediately.
- Prints a final summary line as `Built X/Y tickers`.
- Exits non-zero if any ticker fails.
- Loads persisted dataset + metadata, builds a trend-following long-only strategy, and prints confirmation summaries.
- Saves a deterministic machine-readable artifact file to:
  - `outputs/strategy_plan_<TICKER>_<INTERVAL>.json`

Flags:

- `tickers` (positional): one or more ticker symbols
- `--interval` (required): target strategy interval
- `--category` (optional): `intraday`, `daily`, or `long-term`

Validation:

- If `--category` is provided, it must match the selected `--interval` group.

Generated strategy artifact highlights:

- `strategy_id` and generation timestamp (`generated_at_utc`)
- selected ticker/interval/category
- derived parameter values (moving-average windows, ATR windows/multipliers, breakout level/buffer)
- human-readable entry/exit/stop-loss/take-profit rule text

## Data Normalization

Fetched market data is normalized to lowercase columns where possible:

- `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`

This makes merges and metric pipelines more predictable.

## Storage Layout

Fetched market datasets are stored in efficient machine-readable formats for downstream strategy building:

- Canonical dataset files: `downloads/market/latest_market_<TICKER>_<INTERVAL>.parquet`
- Metadata sidecar files: `downloads/meta/latest_market_<TICKER>_<INTERVAL>.json`

If `--save` is used, user-facing CSV snapshots are still generated in `downloads/` for quick manual inspection.
