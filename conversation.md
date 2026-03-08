# Conversation Notes

- **Project Goal**: Build a reusable Python framework for loading historical strategy reports (CSV), fetching market data via free public endpoints (yfinance), computing basic quantitative metrics, and providing a simple CLI interface. The project should be modular to allow future extensions (new file formats, additional data sources, a web UI).

- **Initial Setup**:
  * Use `pip`/`setuptools` with a `pyproject.toml`.
  * Create a `.gitignore` to exclude typical Python artifacts, virtual‑envs, IDE folders, and caches.
  * Structure:
    - `src/` with subpackages `cli`, `data`, `analysis`, `config`.
    - `tests/` for unit tests.

- **Key Modules**:
  * `src/cli/main.py` – argument‑parser based CLI with commands `load`, `fetch`, `analyze`.
  * `src/data/__init__.py` – wrappers for loading strategy CSVs (`strategy.load_csv`) and fetching market data (`market.fetch_yfinance`).
  * `src/analysis/__init__.py` – basic metrics calculations (mean return, annualised return, volatility, Sharpe ratio).

- **Tests Added**:
  * `tests/test_strategy_loader.py` – tests for successful CSV load and missing file handling.
  * `tests/test_metrics.py` – tests for metrics calculation and error on missing column.

- **Future Directions**:
  * Add support for additional data source protocols via a protocol interface.
  * Expand metrics (max drawdown, Sortino, etc.).
  * Implement a web UI once CLI is stable.

- **Miscellaneous**:
  * The `StrategyReports_SPY_3426.csv` file is a sample strategy report from Thinkorswim.
  * The current implementation uses `pandas` and `yfinance`.
  * `config.py` sets up a cache directory.

- **Fetch Refactor (March 2026)**:
  * `market.fetch_yfinance` now supports both date-range mode (`start`/`end`) and recent-window mode (`period`).
  * Added interval selection for yfinance downloads (including intraday intervals like `1m`, `5m`, `30m`).
  * CLI `fetch` command now supports `--period`, `--interval`, `--auto-adjust`, `--prepost`, and `--actions`.
  * Added validation rules to prevent invalid input combinations (`--period` with date range, `--end` without `--start`).
  * Market output normalization now includes lowercase `date` for easier joins with strategy data.

- **Fetch Output Controls (March 2026)**:
  * Added `--limit N` and `--all` flags for console output control.
  * `--limit` and `--all` are mutually exclusive.
  * If neither `--limit` nor `--all` is provided, fetch output defaults to showing the first 3 and last 3 rows.

- **Saved Snapshot Workflow (March 2026)**:
  * Added `--save` flag on `fetch` to export fetched data to CSV.
  * Snapshot naming convention: `downloads/latest_market_data_<TICKER>.csv`.
  * Ticker names are normalized to a filesystem-safe form when creating filenames.

- **Multi-Ticker Fetch Workflow (March 2026)**:
  * `fetch` now accepts one or more ticker symbols in a single command.
  * Each ticker is fetched as its own yfinance request with the same flags passed to each request.
  * Requests run sequentially with a random 300-500ms delay between completed fetches.
  * With `--save`, old snapshots are cleared once at the start of the run, then one CSV is saved per ticker fetched in that run.

- **Testing Status (March 2026)**:
  * CLI and data-layer tests were expanded to cover interval/period validation, output controls, save behavior, and multi-ticker sequencing.
  * Current suite status after these changes: all tests passing (`29 passed`).

- **Data Layer Refactor (March 2026)**:
  * Market-data responsibilities were split into dedicated modules:
    - `src/data/market_fetcher.py` for yfinance access + normalization
    - `src/data/market_repository.py` for artifact persistence
    - `src/data/market_models.py` for fetch/metadata models
    - `src/data/market_data_access.py` for read-side dataset/metadata loading
  * `src/data/__init__.py` now acts as a thin facade that orchestrates the fetcher and repository while keeping the existing `market.fetch_yfinance(...)` API intact for CLI compatibility.
  * Canonical fetch artifacts are now persisted as:
    - Parquet data in `downloads/market/`
    - JSON metadata in `downloads/meta/`
  * Existing CLI console output and `--save` snapshot UX remain unchanged.

- **A2 Fetch Wiring (March 2026)**:
  * CLI fetch internals were updated to resolve display/export data via `market_data_access` when persisted Parquet artifacts are available.
  * CLI fetch still falls back to the in-memory dataframe returned by `market.fetch_yfinance(...)` if persisted artifacts are missing.
  * Existing tests were refactored to stub read-side data access by default for deterministic behavior.
  * New integration-path tests now verify parquet-first display/export behavior and fallback behavior.
  * Current suite status after A2 updates: all tests passing (`33 passed`).

---

> **Note**: The above notes capture the key decisions and setup steps from this session. They can be referenced or expanded upon as the project evolves.
