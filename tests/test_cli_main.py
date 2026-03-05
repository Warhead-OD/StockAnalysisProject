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

    observed: dict[str, str | None] = {}

    def fake_fetch_yfinance(ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        observed["ticker"] = ticker
        observed["start"] = start
        observed["end"] = end
        return pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})

    monkeypatch.setattr(cli_main.data.market, "fetch_yfinance", fake_fetch_yfinance)

    cli_main.main(["fetch", "AAPL", "--start", "2026-01-01", "--end", "2026-01-31"])

    out = capsys.readouterr().out
    assert observed == {"ticker": "AAPL", "start": "2026-01-01", "end": "2026-01-31"}
    assert "adj_close" in out


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
    assert "Ticker symbol" in result.stdout
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
    assert "Ticker symbol" in result.stdout
    assert "ImportError" not in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
