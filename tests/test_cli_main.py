"""
Regression tests for CLI command routing and output formatting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

import src.cli.main as cli_main
import src.analysis as analysis
from src.analysis.thinkscript_models import ThinkScriptExportRequest, ThinkScriptExportResult
from src.data.market_models import MarketDatasetMetadata


def _sample_market_df() -> pd.DataFrame:
    """Build a small normalized market dataframe used across CLI tests."""

    rows = 80
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=rows, freq="D").strftime("%Y-%m-%d"),
            "open": [100.0 + idx * 0.2 for idx in range(rows)],
            "high": [100.8 + idx * 0.2 for idx in range(rows)],
            "low": [99.2 + idx * 0.2 for idx in range(rows)],
            "close": [100.4 + idx * 0.2 for idx in range(rows)],
            "adj_close": [100.4 + idx * 0.2 for idx in range(rows)],
        }
    )


def _sample_strategy_payload(
    *,
    ticker: str = "AAPL",
    interval: str = "1d",
    category: str = "daily",
) -> dict[str, object]:
    """Build a minimal strategy artifact payload dict for CLI tests."""

    return {
        "strategy_id": f"trend_following_{ticker.upper()}_{interval}",
        "generated_at_utc": "2026-03-10T10:20:21Z",
        "ticker": ticker,
        "interval": interval,
        "category": category,
        "data_row_count": 80,
        "status": "generated",
        "rules": {
            "name": "Trend Following (Price Action)",
            "style": "trend-following",
            "direction": "long-only",
            "entry_rule": "Enter long when close is above fast MA and fast MA is above slow MA, breakout above swing high.",
            "exit_rule": "Exit long when close falls below fast MA.",
            "stop_loss_rule": "Stop at entry minus ATR * stop_atr_multiplier.",
            "take_profit_rule": "TP at entry plus ATR * take_profit_atr_multiplier.",
        },
        "parameters": {
            "fast_window": 20,
            "slow_window": 50,
            "breakout_window": 20,
            "atr_window": 14,
            "stop_atr_multiplier": 1.9,
            "take_profit_atr_multiplier": 3.2,
            "trend_strength": 0.027,
            "breakout_level": 116.6,
            "breakout_buffer": 0.16,
            "atr": 1.6,
            "max_position_value": None,
        },
    }


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
        row_count=80,
    )


@pytest.fixture(autouse=True)
def _stub_market_data_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default stubs for data-access and ThinkScript export unless a test overrides them."""

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

    def _stub_export_thinkscript_scaffold(
        *,
        request: ThinkScriptExportRequest,
        strategy_artifact_path: Path,
        output_path: Path,
    ) -> ThinkScriptExportResult:
        raise RuntimeError("export_thinkscript_scaffold should not be called in this test")

    monkeypatch.setattr(
        cli_main.analysis,
        "export_thinkscript_scaffold",
        _stub_export_thinkscript_scaffold,
    )

    def _stub_export_thinkscript(
        *,
        ticker: str,
        interval: str,
        export_mode: str = "strategy",
        include_orders: bool = True,
    ) -> ThinkScriptExportResult:
        raise RuntimeError("export_thinkscript should not be called in this test")

    monkeypatch.setattr(
        cli_main.analysis,
        "export_thinkscript",
        _stub_export_thinkscript,
    )


def test_main_analyze_loads_strategy_from_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Analyze should load strategy directly from file and run metrics and refinement."""

    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    monkeypatch.setattr(cli_main.data, "load_strategy_from_file", lambda _path: strategy_df)

    monkeypatch.setattr(
        cli_main.data.market,
        "get_loaded",
        lambda: (_ for _ in ()).throw(RuntimeError("No market data has been fetched yet")),
    )
    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: True)
    monkeypatch.setattr(cli_main.data.market_data_access, "load_dataset", lambda **_kwargs: market_df)

    monkeypatch.setattr(cli_main.analysis.metrics, "compute_all", lambda _df: {"sharpe_ratio": 0.5})
    monkeypatch.setattr(
        cli_main.thinkscript_artifact,
        "load_artifact_payload_optional",
        lambda *, ticker, interval: _sample_strategy_payload(ticker=ticker, interval=interval, category="daily"),
    )

    cli_main.main(["analyze", "demo-strategy", "AAPL", "--file", "report.csv", "--interval", "1d"])

    out = capsys.readouterr().out
    assert "sharpe_ratio: 0.5000" in out
    assert "Refinement scaffold: status=scaffold" in out


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


def test_parse_args_build_strategy_command() -> None:
    """Test parsing build-strategy command arguments."""

    args = cli_main._parse_args(["build-strategy", "AAPL", "MSFT", "--interval", "1d", "--category", "daily"])

    assert args.command == "build-strategy"
    assert args.tickers == ["AAPL", "MSFT"]
    assert args.interval == "1d"
    assert args.category == "daily"


def test_parse_args_build_strategy_rejects_category_interval_mismatch() -> None:
    """Test parser rejects mismatched strategy category and interval selections."""

    with pytest.raises(SystemExit):
        cli_main._parse_args(["build-strategy", "AAPL", "--interval", "1d", "--category", "intraday"])


def test_main_build_strategy_requires_existing_market_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test build-strategy exits with error when required fetched dataset is missing."""

    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: False)

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["build-strategy", "AAPL", "--interval", "1d"])

    captured = capsys.readouterr()
    err = captured.err
    out = captured.out
    assert exc.value.code == 1
    assert "required fetched market data was not found" in err
    assert "Built 0/1 tickers" in out


def test_main_build_strategy_loads_dataset_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test build-strategy scaffold loads persisted data artifacts when available."""

    monkeypatch.setattr(cli_main.data.market_data_access, "has_dataset", lambda **_kwargs: True)
    monkeypatch.setattr(cli_main.data.market_data_access, "load_dataset", lambda **_kwargs: _sample_market_df())
    monkeypatch.setattr(
        cli_main.data.market_data_access,
        "load_metadata",
        lambda **_kwargs: _sample_metadata(ticker="AAPL", interval="1d"),
    )
    written: dict[str, str] = {}

    def fake_write_text(self: Path, text: str, encoding: str = "utf-8") -> int:
        written[str(self)] = text
        return len(text)

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    cli_main.main(["build-strategy", "AAPL", "--interval", "1d", "--category", "daily"])

    out = capsys.readouterr().out
    assert "Built strategy trend_following_AAPL_1d" in out
    assert "rows=80, status=generated" in out
    assert "Saved strategy artifact to" in out
    assert "Built 1/1 tickers" in out

    assert len(written) == 1
    artifact_path = next(iter(written.keys()))
    payload = json.loads(next(iter(written.values())))
    assert artifact_path.endswith("outputs\\strategy_plan_AAPL_1d.json")
    assert payload["strategy_id"] == "trend_following_AAPL_1d"
    assert payload["status"] == "generated"
    assert payload["category"] == "daily"
    assert payload["rules"]["style"] == "trend-following"


def test_main_build_strategy_multi_ticker_mixed_results(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """build-strategy should continue per ticker, emit immediate errors, and summarize totals."""

    monkeypatch.setattr(
        cli_main.data.market_data_access,
        "has_dataset",
        lambda **kwargs: kwargs["ticker"] == "AAPL",
    )
    monkeypatch.setattr(cli_main.data.market_data_access, "load_dataset", lambda **_kwargs: _sample_market_df())
    monkeypatch.setattr(
        cli_main.data.market_data_access,
        "load_metadata",
        lambda **kwargs: _sample_metadata(ticker=kwargs["ticker"], interval=kwargs["interval"]),
    )

    written: dict[str, str] = {}

    def fake_write_text(self: Path, text: str, encoding: str = "utf-8") -> int:
        written[str(self)] = text
        return len(text)

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["build-strategy", "AAPL", "MSFT", "--interval", "1d", "--category", "daily"])

    captured = capsys.readouterr()
    out = captured.out
    err = captured.err

    assert exc.value.code == 1
    assert "Built strategy trend_following_AAPL_1d" in out
    assert "Built 1/2 tickers" in out
    assert "[MSFT] Cannot run build-strategy: required fetched market data was not found" in err

    assert len(written) == 1
    artifact_path = next(iter(written.keys()))
    assert artifact_path.endswith("outputs\\strategy_plan_AAPL_1d.json")


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

    cli_main.data.market_repository.clear_saved_fetch_snapshots(output_dir=tmp_path)

    assert not old_a.exists()
    assert not old_b.exists()


def test_save_fetched_data_supports_multiple_tickers_after_cleanup(tmp_path: Path) -> None:
    """Test save helper keeps one CSV per ticker when cleanup is done once per run."""

    df_aapl = pd.DataFrame({"date": ["2026-01-01"], "adj_close": [100.0]})
    df_msft = pd.DataFrame({"date": ["2026-01-02"], "adj_close": [101.0]})

    cli_main.data.market_repository.clear_saved_fetch_snapshots(output_dir=tmp_path)
    first_path = cli_main.data.market_repository.save_market_snapshot_csv(
        df=df_aapl,
        ticker="AAPL",
        output_dir=tmp_path,
    )
    assert first_path.name == "latest_market_data_AAPL.csv"
    assert first_path.exists()

    second_path = cli_main.data.market_repository.save_market_snapshot_csv(
        df=df_msft,
        ticker="MSFT",
        output_dir=tmp_path,
    )
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

    monkeypatch.setattr(cli_main.data.market_repository, "clear_saved_fetch_snapshots", fake_clear)
    monkeypatch.setattr(
        cli_main.data.market_repository,
        "save_market_snapshot_csv",
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
    monkeypatch.setattr(cli_main.data.market_repository, "clear_saved_fetch_snapshots", lambda output_dir=None: None)

    def fake_save(df: pd.DataFrame, ticker: str, output_dir=None) -> Path:
        observed["df"] = df
        return Path(f"downloads/latest_market_data_{ticker}.csv")

    monkeypatch.setattr(cli_main.data.market_repository, "save_market_snapshot_csv", fake_save)
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

    strategy_df = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-01-02"]), "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    monkeypatch.setattr(cli_main.data, "load_strategy_from_file", lambda _path: strategy_df)
    monkeypatch.setattr(cli_main.data.market, "get_loaded", lambda: market_df)

    def fake_compute_all(df: pd.DataFrame) -> dict[str, float]:
        assert list(df.columns) == ["date", "return", "adj_close"]
        assert len(df) == 2
        return {"sharpe_ratio": 1.23456, "annualized_return": 0.11111}

    monkeypatch.setattr(cli_main.analysis.metrics, "compute_all", fake_compute_all)

    cli_main.main(["analyze", "demo-strategy", "SPY", "--file", "report.csv"])

    out = capsys.readouterr().out
    assert "sharpe_ratio: 1.2346" in out
    assert "annualized_return: 0.1111" in out


def test_parse_args_analyze_interval_default_and_override() -> None:
    """Analyze supports optional --interval with default and explicit override."""

    default_args = cli_main._parse_args(["analyze", "demo-strategy", "SPY", "--file", "report.csv"])
    custom_args = cli_main._parse_args(["analyze", "demo-strategy", "SPY", "--file", "report.csv", "--interval", "1wk"])

    assert default_args.interval == "1d"
    assert custom_args.interval == "1wk"


def test_main_analyze_runs_refinement_scaffold(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Analyze should invoke refinement scaffold and print scaffold summary lines."""

    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    monkeypatch.setattr(cli_main.data, "load_strategy_from_file", lambda _path: strategy_df)
    monkeypatch.setattr(cli_main.data.market, "get_loaded", lambda: market_df)

    observed_call = {}

    def fake_workflow(
        *,
        strategy_name,
        ticker,
        interval,
        strategy_df,
        market_df,
        strategy_payload,
    ):
        observed_call["strategy_name"] = strategy_name
        observed_call["ticker"] = ticker
        observed_call["interval"] = interval
        observed_call["strategy_payload"] = strategy_payload
        return (
            {"sharpe_ratio": 1.0},
            cli_main.analysis.StrategyRefinementResult.scaffold(
                strategy_name=strategy_name,
                ticker=ticker,
                interval=interval,
                summary="scaffold summary",
                suggestions=["one", "two"],
                strategy_id="trend_following_SPY_1d",
            ),
        )

    monkeypatch.setattr(cli_main.analysis, "run_analyze_workflow", fake_workflow)

    cli_main.main(["analyze", "demo-strategy", "SPY", "--file", "report.csv", "--interval", "1d"])

    out = capsys.readouterr().out
    assert "sharpe_ratio: 1.0000" in out
    assert "Refinement scaffold: status=scaffold, suggestions=2, interval=1d" in out
    assert "scaffold summary" in out
    assert "- one" in out
    assert "- two" in out
    assert observed_call["strategy_name"] == "demo-strategy"
    assert observed_call["ticker"] == "SPY"
    assert observed_call["interval"] == "1d"


def test_main_analyze_skips_refinement_when_artifact_load_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Analyze still prints metrics when strategy artifact payload cannot be loaded."""

    strategy_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "return": [0.01, -0.02]})
    market_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "adj_close": [100.0, 99.0]})

    monkeypatch.setattr(cli_main.data, "load_strategy_from_file", lambda _path: strategy_df)
    monkeypatch.setattr(cli_main.data.market, "get_loaded", lambda: market_df)

    def fake_workflow(**kwargs):
        raise ValueError("bad artifact payload")

    monkeypatch.setattr(cli_main.analysis, "run_analyze_workflow", fake_workflow)

    cli_main.main(["analyze", "demo-strategy", "SPY", "--file", "report.csv", "--interval", "1d"])

    captured = capsys.readouterr()
    out = captured.out
    err = captured.err
    assert "Skipped refinement scaffold: bad artifact payload" in err


def test_parse_args_export_thinkscript_command() -> None:
    """Test parsing export-thinkscript command with defaults and explicit flags."""

    args = cli_main._parse_args(["export-thinkscript", "AAPL", "MSFT", "--interval", "1d"])

    assert args.command == "export-thinkscript"
    assert args.tickers == ["AAPL", "MSFT"]
    assert args.interval == "1d"
    assert args.mode == "strategy"
    assert args.disable_orders is False


def test_parse_args_export_thinkscript_study_mode_and_disable_orders() -> None:
    """Test parsing export-thinkscript with --mode study and --disable-orders."""

    args = cli_main._parse_args(
        ["export-thinkscript", "SPY", "--interval", "1wk", "--mode", "study", "--disable-orders"]
    )

    assert args.mode == "study"
    assert args.disable_orders is True


def test_main_export_thinkscript_calls_exporter_and_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test export-thinkscript routes to exporter and prints success summary."""

    fake_result = ThinkScriptExportResult.generated(
        ticker="AAPL",
        interval="1d",
        export_mode="strategy",
        include_orders=True,
        output_path="outputs/thinkscript_AAPL_1d_strategy.txt",
        strategy_id="trend_following_AAPL_1d",
        generated_at="2026-03-15T00:00:00Z",
    )

    monkeypatch.setattr(
        cli_main.analysis,
        "export_thinkscript",
        lambda *, ticker, interval, export_mode="strategy", include_orders=True: fake_result,
    )

    cli_main.main(["export-thinkscript", "AAPL", "--interval", "1d"])

    out = capsys.readouterr().out
    assert "Exported ThinkScript for AAPL" in out
    assert "1d" in out
    assert "mode=strategy" in out
    assert "status=generated" in out
    assert "thinkscript_AAPL_1d_strategy.txt" in out


def test_main_export_thinkscript_missing_artifact_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test export-thinkscript exits with code 1 when strategy artifact is missing."""

    monkeypatch.setattr(
        cli_main.analysis,
        "export_thinkscript",
        lambda *, ticker, interval, export_mode="strategy", include_orders=True: (_ for _ in ()).throw(
            FileNotFoundError("Strategy artifact not found: outputs/strategy_plan_AAPL_1d.json")
        ),
    )

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["export-thinkscript", "AAPL", "--interval", "1d"])

    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert "Failed to export ThinkScript" in err


def test_main_export_thinkscript_multi_ticker_calls_merge_and_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Multi-ticker export-thinkscript should merge artifacts and export a single MULTI script."""

    merged_payload = {
        "strategy_id": "trend_following_MULTI_1d",
        "ticker": "MULTI",
        "interval": "1d",
        "category": "daily",
        "status": "generated",
        "parameters": {
            "fast_window": 20,
            "slow_window": 50,
            "breakout_window": 20,
            "atr_window": 14,
            "stop_atr_multiplier": 1.9,
            "take_profit_atr_multiplier": 3.2,
        },
        "merged_tickers": ["AAPL", "MSFT"],
        "skipped_tickers": {"NVDA": "Strategy artifact not found for NVDA (1d)"},
    }

    fake_result = ThinkScriptExportResult.generated(
        ticker="MULTI",
        interval="1d",
        export_mode="strategy",
        include_orders=True,
        output_path="outputs/thinkscript_MULTI_1d_strategy.txt",
        strategy_id="trend_following_MULTI_1d",
        generated_at="2026-03-15T00:00:00Z",
    )

    monkeypatch.setattr(
        cli_main.analysis,
        "run_merge_thinkscript_artifacts_workflow",
        lambda *, tickers, interval: merged_payload,
    )
    monkeypatch.setattr(
        cli_main.analysis,
        "export_thinkscript_from_payload",
        lambda *, strategy_payload, ticker, interval, export_mode="strategy", include_orders=True: fake_result,
    )

    cli_main.main(["export-thinkscript", "AAPL", "MSFT", "NVDA", "--interval", "1d"])

    captured = capsys.readouterr()
    out = captured.out
    err = captured.err
    assert "Merged strategy artifacts for 2/3 tickers into unified export." in out
    assert "Exported ThinkScript for MULTI" in out
    assert "thinkscript_MULTI_1d_strategy.txt" in out
    assert "[NVDA] Strategy artifact not found for NVDA (1d)" in err


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
