"""
Regression tests for CLI command routing and output formatting.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

import src.cli.main as cli_main
from src.data.market_models import MarketDatasetMetadata


def _sample_market_df() -> pd.DataFrame:
    """Build a small normalized market dataframe used across CLI tests."""

    return pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 101.0]})


def _sample_metadata(*, ticker: str = "AAPL", interval: str = "1d") -> MarketDatasetMetadata:
    """Build representative dataset metadata for CLI tests."""

    return MarketDatasetMetadata(
        ticker=ticker,
        interval=interval,
        period="5d",
        start=None,
        end=None,
        auto_adjust=False,
        prepost=False,
        actions=False,
        exchange_timezone="America/New_York",
        fetched_at_utc="2026-03-10T00:00:00Z",
        row_count=2,
    )


@pytest.fixture(autouse=True)
def _stub_market_data_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to in-memory fetch frames unless a test overrides data-access behavior."""

    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: False)
    monkeypatch.setattr(
        cli_main.data.market_data_access,
        "load_dataset",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("load_dataset should not be called in this test")),
    )
    monkeypatch.setattr(
        cli_main.data.market_data_access,
        "load_metadata",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("load_metadata should not be called in this test")),
    )


def test_parse_args_load_command() -> None:
    """
    Test parsing of 'load' command arguments.
    Verifies correct command and file path are parsed.
    """

    args = cli_main._parse_args(["load", "--file", "report.csv"])

    assert args.command == "load"
    assert args.file == Path("report.csv")


def test_main_load_calls_strategy_loader(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Test that main() calls strategy loader and prints correct output for 'load' command.
    """

    observed: dict[str, Path] = {}

    def fake_load_csv(path: Path) -> pd.DataFrame:
        observed["path"] = path
        return pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.1, -0.1]})

    monkeypatch.setattr(cli_main.data.strategy, "load_csv", fake_load_csv)

    cli_main.main(["load", "--file", "report.csv"])

    out = capsys.readouterr().out
    assert observed["path"] == Path("report.csv")
    assert "Loaded strategy with 2 rows" in out


def test_main_fetch_passes_arguments(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Test that main() passes correct arguments to fetch_yfinance and prints output for 'fetch' command.
    """

    observed_calls: list[dict[str, str | bool | None]] = []

    def fake_fetch_yfinance(
        ticker: str,
        start: str | None,
        end: str | None,
        *,
        period: str | None,
        interval: str,
        auto_adjust: bool,
        prepost: bool,
        actions: bool,
    ) -> pd.DataFrame:
        observed_calls.append(
            {
                "ticker": ticker,
                "start": start,
                "end": end,
                "period": period,
                "interval": interval,
                "auto_adjust": auto_adjust,
                "prepost": prepost,
                "actions": actions,
            }
        )
        return pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(
        [
            "fetch",
            "AAPL",
            "--start",
            "2026-01-01",
            "--end",
            "2026-01-31",
            "--interval",
            "30m",
            "--auto-adjust",
            "--prepost",
            "--actions",
        ]
    )

    out = capsys.readouterr().out
    assert observed_calls == [
        {
            "ticker": "AAPL",
            "start": "2026-01-01",
            "end": "2026-01-31",
            "period": None,
            "interval": "30m",
            "auto_adjust": True,
            "prepost": True,
            "actions": True,
        }
    ]
    assert "adj_close" in out


def test_parse_args_fetch_period_mode() -> None:
    """Test parsing period mode and default fetch options."""

    args = cli_main._parse_args(["fetch", "MSFT", "--period", "5d", "--interval", "5m"])

    assert args.command == "fetch"
    assert args.tickers == ["MSFT"]
    assert args.period == "5d"
    assert args.interval == "5m"
    assert args.start is None
    assert args.end is None


def test_parse_args_fetch_rejects_mixing_period_with_dates() -> None:
    """Test invalid period/date combination exits with parser error."""

    with pytest.raises(SystemExit):
        cli_main._parse_args(
            [
                "fetch",
                "SPY",
                "--period",
                "1mo",
                "--start",
                "2026-01-01",
            ]
        )


def test_parse_args_fetch_rejects_end_without_start() -> None:
    """Test that --end without --start exits with parser error."""

    with pytest.raises(SystemExit):
        cli_main._parse_args(["fetch", "SPY", "--end", "2026-01-31"])


def test_parse_args_fetch_limit_and_all_are_mutually_exclusive() -> None:
    """Test that --limit and --all cannot be used together."""

    with pytest.raises(SystemExit):
        cli_main._parse_args(["fetch", "SPY", "--limit", "10", "--all"])


def test_parse_args_fetch_limit_must_be_positive() -> None:
    """Test that --limit must be a positive integer."""

    with pytest.raises(SystemExit):
        cli_main._parse_args(["fetch", "SPY", "--limit", "0"])


def test_parse_args_fetch_save_flag() -> None:
    """Test parsing of --save fetch flag."""

    args = cli_main._parse_args(["fetch", "SPY", "--save"])
    assert args.save is True


def test_parse_args_fetch_multiple_tickers() -> None:
    """Test parsing of multiple ticker symbols for fetch."""

    args = cli_main._parse_args(["fetch", "SPY", "QQQ", "IWM"])
    assert args.tickers == ["SPY", "QQQ", "IWM"]


def test_main_fetch_default_prints_first_and_last_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test default fetch output shows summary plus first and last rows for long datasets."""

    def fake_fetch_yfinance(
        ticker: str,
        start: str | None,
        end: str | None,
        *,
        period: str | None,
        interval: str,
        auto_adjust: bool,
        prepost: bool,
        actions: bool,
    ) -> pd.DataFrame:
        return pd.DataFrame({"date": [f"2026-01-{idx:02d}" for idx in range(1, 11)], "adj_close": list(range(10))})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL"])

    out = capsys.readouterr().out
    assert "Fetched 10 rows. Showing first 3 and last 3 rows." in out
    assert "2026-01-01" in out
    assert "2026-01-10" in out


def test_main_fetch_limit_prints_requested_head_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test --limit prints only the first N rows."""

    def fake_fetch_yfinance(
        ticker: str,
        start: str | None,
        end: str | None,
        *,
        period: str | None,
        interval: str,
        auto_adjust: bool,
        prepost: bool,
        actions: bool,
    ) -> pd.DataFrame:
        return pd.DataFrame({"date": [f"2026-01-{idx:02d}" for idx in range(1, 11)], "adj_close": list(range(10))})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL", "--limit", "2"])

    out = capsys.readouterr().out
    assert "2026-01-01" in out
    assert "2026-01-02" in out
    assert "2026-01-10" not in out


def test_clear_saved_fetch_data_removes_old_snapshots(tmp_path: Path) -> None:
    """Test cleanup helper removes previous snapshot files."""

    old_a = tmp_path / "latest_market_data_AAPL.csv"
    old_b = tmp_path / "latest_market_data_MSFT.csv"
    old_a.write_text("date,adj_close\n2026-01-01,100\n", encoding="utf-8")
    old_b.write_text("date,adj_close\n2026-01-01,101\n", encoding="utf-8")

    cli_main._clear_saved_fetch_data(output_dir=tmp_path)

    assert not old_a.exists()
    assert not old_b.exists()


def test_save_fetched_data_supports_multiple_tickers_after_cleanup(tmp_path: Path) -> None:
    """Test save helper keeps one CSV per ticker when cleanup is done once per run."""

    df_aapl = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})
    df_msft = pd.DataFrame({"date": ["2026-01-02"], "adj_close": [101.0]})

    cli_main._clear_saved_fetch_data(output_dir=tmp_path)
    first_path = cli_main._save_fetched_data(df=df_aapl, ticker="AAPL", output_dir=tmp_path)
    assert first_path.name == "latest_market_data_AAPL.csv"
    assert first_path.exists()

    second_path = cli_main._save_fetched_data(df=df_msft, ticker="MSFT", output_dir=tmp_path)
    assert second_path.name == "latest_market_data_MSFT.csv"
    assert second_path.exists()
    assert first_path.exists()

    saved_files = list(tmp_path.glob("latest_market_data_*.csv"))
    assert len(saved_files) == 2
    assert {file.name for file in saved_files} == {
        "latest_market_data_AAPL.csv",
        "latest_market_data_MSFT.csv",
    }


def test_main_fetch_save_calls_helper(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test --save triggers file-save helper and prints destination."""

    def fake_fetch_yfinance(
        ticker: str,
        start: str | None,
        end: str | None,
        *,
        period: str | None,
        interval: str,
        auto_adjust: bool,
        prepost: bool,
        actions: bool,
    ) -> pd.DataFrame:
        return pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)
    clear_called = {"count": 0}

    def fake_clear(output_dir=None):
        clear_called["count"] += 1

    monkeypatch.setattr(cli_main, "_clear_saved_fetch_data", fake_clear)
    monkeypatch.setattr(
        cli_main,
        "_save_fetched_data",
        lambda df, ticker, output_dir=None: Path(f"downloads/latest_market_data_{ticker}.csv"),
    )
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL", "MSFT", "--save"])

    out = capsys.readouterr().out
    assert clear_called["count"] == 1
    assert "Saved fetched data to" in out
    assert "latest_market_data_AAPL.csv" in out
    assert "latest_market_data_MSFT.csv" in out


def test_main_fetch_multiple_tickers_waits_between_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test multi-ticker fetch waits 300-500ms between sequential requests."""

    call_order: list[str] = []
    sleep_values: list[float] = []

    def fake_fetch_yfinance(
        ticker: str,
        start: str | None,
        end: str | None,
        *,
        period: str | None,
        interval: str,
        auto_adjust: bool,
        prepost: bool,
        actions: bool,
    ) -> pd.DataFrame:
        call_order.append(ticker)
        return pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.37)
    monkeypatch.setattr(cli_main.time, "sleep", lambda seconds: sleep_values.append(seconds))

    cli_main.main(["fetch", "AAPL", "MSFT", "NVDA", "--limit", "1"])

    assert call_order == ["AAPL", "MSFT", "NVDA"]
    assert sleep_values == [0.37, 0.37]


def test_main_fetch_uses_parquet_data_when_available(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test fetch output prefers persisted parquet data when available."""

    fetched_df = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})
    parquet_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [200.0, 201.0]})

    monkeypatch.setattr(
        cli_main.data.market,
        "fetch_yfinance",
        lambda *args, **kwargs: fetched_df,
    )
    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: True)
    monkeypatch.setattr(cli_main.data.market_data_access, "load_dataset", lambda **_kwargs: parquet_df)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL", "--all"])

    out = capsys.readouterr().out
    assert "200.0" in out
    assert "201.0" in out
    assert "100.0" not in out


def test_main_fetch_save_uses_resolved_dataframe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test --save writes the resolved dataframe used for console output."""

    fetched_df = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})
    parquet_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [200.0, 201.0]})
    observed: dict[str, pd.DataFrame] = {}

    monkeypatch.setattr(
        cli_main.data.market,
        "fetch_yfinance",
        lambda *args, **kwargs: fetched_df,
    )
    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: True)
    monkeypatch.setattr(cli_main.data.market_data_access, "load_dataset", lambda **_kwargs: parquet_df)
    monkeypatch.setattr(cli_main, "_clear_saved_fetch_data", lambda output_dir=None: None)

    def fake_save(df: pd.DataFrame, ticker: str, output_dir=None) -> Path:
        observed["df"] = df
        return Path(f"downloads/latest_market_data_{ticker}.csv")

    monkeypatch.setattr(cli_main, "_save_fetched_data", fake_save)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL", "--save", "--limit", "1"])

    out = capsys.readouterr().out
    assert "Saved fetched data to" in out
    assert observed["df"].equals(parquet_df)


def test_main_fetch_falls_back_when_parquet_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test fetch uses yfinance dataframe when persisted parquet is unavailable."""

    fetched_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [123.0, 124.0]})

    monkeypatch.setattr(
        cli_main.data.market,
        "fetch_yfinance",
        lambda *args, **kwargs: fetched_df,
    )
    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: False)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.random, "uniform", lambda _a, _b: 0.4)

    cli_main.main(["fetch", "AAPL", "--all"])

    out = capsys.readouterr().out
    assert "123.0" in out
    assert "124.0" in out


def test_main_analyze_merges_and_prints_metrics(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Test that main() merges strategy and market data and prints metrics for 'analyze' command.
    """

    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    monkeypatch.setattr(cli_main.data.strategy, "get_loaded", lambda: strategy_df)
    monkeypatch.setattr(cli_main.data.market, "get_loaded", lambda: market_df)

    def fake_compute_all(df: pd.DataFrame) -> dict[str, float]:
        assert list(df.columns) == ["date", "return", "adj_close"]
        return {"sharpe_ratio": 1.23456, "annualized_return": 0.11111}

    monkeypatch.setattr(cli_main.analysis.metrics, "compute_all", fake_compute_all)

    cli_main.main(["analyze", "demo-strategy", "SPY"])

    out = capsys.readouterr().out
    assert "sharpe_ratio: 1.2346" in out
    assert "annualized_return: 0.1111" in out


def test_main_unknown_command_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Test that main() exits with error for unknown command.
    """

    monkeypatch.setattr(cli_main, "_parse_args", lambda _argv: argparse.Namespace(command="unknown"))

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["unknown"])

    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert "Unknown command" in err


def test_module_entrypoint_help_runs_without_runtime_warning() -> None:
    """
    Test that module entrypoint help runs without runtime warning.
    """

    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "fetch", "-h"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert "ticker symbols" in result.stdout.lower()
    assert "RuntimeWarning" not in result.stderr


def test_script_entrypoint_help_runs_without_import_errors() -> None:
    """
    Test that script entrypoint help runs without import errors.
    """

    result = subprocess.run(
        [sys.executable, "src/cli/main.py", "fetch", "-h"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert "ticker symbols" in result.stdout.lower()
    assert "ImportError" not in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
