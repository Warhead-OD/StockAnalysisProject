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

---

> **Note**: The above notes capture the key decisions and setup steps from this session. They can be referenced or expanded upon as the project evolves.
