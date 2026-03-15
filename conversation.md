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

- **B1 Build-Strategy Scaffold (March 2026)**:
  * Added new CLI command scaffold: `build-strategy`.
  * Added required arguments for single-ticker workflow:
    - positional `ticker`
    - required `--interval`
    - optional `--category` (`intraday`, `daily`, `long-term`)
  * Added parser-level validation ensuring that `--category` (when provided) matches the implied category for `--interval`.
  * Added runtime preflight validation requiring fetched artifacts to exist for the selected ticker/interval before running strategy build flow.
  * Current scaffold loads persisted dataset + metadata and prints a confirmation summary (strategy generation logic to follow in later slices).
  * CLI tests were expanded to cover build-strategy parsing, mismatch validation, missing-data failure behavior, and successful preflight loading behavior.
  * Current suite status after B1 scaffold updates: all tests passing (`37 passed`).

- **B2 Trend-Following Generation (March 2026)**:
  * Added strategy-building contracts and scaffolding modules:
    - `src/analysis/strategy_models.py`
    - `src/analysis/strategy_builder.py`
  * Implemented initial trend-following (price action) strategy generation for single ticker/interval builds.
  * Builder now derives core parameters from market candles (moving averages, breakout windows, ATR-derived stop/take-profit multipliers) and emits concrete long-only entry/exit/SL/TP rule descriptions.
  * `build-strategy` CLI now runs the strategy builder and writes deterministic JSON artifacts to:
    - `outputs/strategy_plan_<TICKER>_<INTERVAL>.json`
  * Added dedicated unit tests for strategy builder success/error paths in `tests/test_strategy_builder.py`.
  * Strengthened CLI integration tests to validate generated artifact payload structure and deterministic output naming.
  * Current suite status after B2 updates: all tests passing (`41 passed`).

---

> **Note**: The above notes capture the key decisions and setup steps from this session. They can be referenced or expanded upon as the project evolves.

- **C1 ThinkScript Exporter v1 (March 2026)**:
  * Added new CLI command: `export-thinkscript`.
  * Required arguments:
    - positional `ticker`
    - required `--interval`
  * Optional flags: `--mode` (`strategy` | `study`, default `strategy`), `--disable-orders`.
  * Added new analysis modules:
    - `src/analysis/thinkscript_models.py` — `ThinkScriptExportRequest`, `ThinkScriptExportResult` (with `scaffold()` and `generated()` classmethods)
    - `src/analysis/thinkscript_exporter.py` — `_build_thinkscript_source()` renderer + `export_thinkscript_scaffold()` function
  * ThinkScript output is a fully rendered script with:
    - Header comment block (strategy ID, ticker/interval/mode/orders, generation timestamp)
    - `declare upper;`
    - Six `input` declarations (fast/slow MA windows, breakout lookback, ATR window, stop and TP ATR multipliers)
    - `def` blocks for MAs, ATR, swing-high, entry/exit conditions
    - `plot BuyArrow` / `plot SellArrow` with `ARROW_UP` / `ARROW_DOWN` painting strategies
    - `plot FastMALine` / `plot SlowMALine` overlay plots
    - `AddOrder()` block — present only when `mode=strategy` and `--disable-orders` is not set
  * Output artifact naming: `outputs/thinkscript_<TICKER>_<INTERVAL>_<MODE>.txt`.
  * `export_thinkscript_scaffold()` raises `FileNotFoundError` if the strategy artifact does not exist.
  * Added dedicated unit tests in `tests/test_thinkscript_exporter.py` covering template rendering, order block inclusion/suppression, study mode, missing artifact, and directory creation.
  * Extended CLI tests in `tests/test_cli_main.py` with parse, success, and missing-artifact failure paths for `export-thinkscript`.
  * Extended autouse stub fixture to guard `export_thinkscript_scaffold` across all tests by default.
  * Current suite status after C1 updates: all tests passing (`54 passed`).

- **D1 Analyze Refinement Flow (March 2026)**:
  * Added new refinement contracts and module:
    - `src/analysis/strategy_refinement_models.py` — `StrategyRefinementRequest`, `StrategyRefinementResult`
    - `src/analysis/strategy_refiner.py` — `refine_strategy_from_report_scaffold(...)`
  * `analyze` command now supports `--interval` (default `1d`) for resolving strategy artifacts during refinement.
  * Added strategy artifact loader helper in CLI:
    - `_load_strategy_artifact_payload(ticker, interval)`
  * Analyze flow now:
    - computes and prints baseline metrics (existing behavior)
    - attempts to load `outputs/strategy_plan_<TICKER>_<INTERVAL>.json`
    - runs refinement scaffold and prints status, summary, and recommendation bullet lines
  * Refinement recommendation logic is now artifact-aware:
    - uses artifact parameters when available (`fast_window`, `slow_window`, `breakout_window`, ATR multipliers)
    - branches suggestions using report win-rate and expectancy
    - falls back to guidance when artifact is missing
  * Added/expanded test coverage:
    - `tests/test_strategy_refiner.py`: artifact-present, artifact-missing, low win-rate, positive expectancy, invalid-parameter fallback
    - `tests/test_cli_main.py`: analyze interval parsing, analyze refinement invocation, non-fatal skip path when artifact loading fails
  * Added dedicated D1.1a fix step to resolve typing/error issue in `tests/test_cli_main.py` capture assertions.
  * Current suite status after D1 updates: all tests passing (`62 passed`).
