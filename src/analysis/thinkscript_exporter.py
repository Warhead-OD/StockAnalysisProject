"""ThinkScript exporter — converts strategy JSON artifacts into ThinkScript scripts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .thinkscript_models import ThinkScriptExportRequest, ThinkScriptExportResult


def _build_thinkscript_source(
    *,
    strategy_payload: dict[str, object],
    request: ThinkScriptExportRequest,
    generated_at: str,
) -> str:
    """Render a rule-driven ThinkScript source from a strategy artifact payload."""

    params = strategy_payload.get("parameters") or {}
    strategy_id = str(strategy_payload.get("strategy_id", "unknown"))
    emit_orders = request.export_mode == "strategy" and request.include_orders

    fast_window = int(params.get("fast_window", 20))  # type: ignore[arg-type]
    slow_window = int(params.get("slow_window", 50))  # type: ignore[arg-type]
    breakout_window = int(params.get("breakout_window", 20))  # type: ignore[arg-type]
    atr_window = int(params.get("atr_window", 14))  # type: ignore[arg-type]
    stop_mult = float(params.get("stop_atr_multiplier", 1.9))  # type: ignore[arg-type]
    tp_mult = float(params.get("take_profit_atr_multiplier", 3.2))  # type: ignore[arg-type]

    lines: list[str] = [
        f"# ThinkScript {request.export_mode.title()}: {strategy_id}",
        f"# ticker={request.ticker}  interval={request.interval}"
        f"  mode={request.export_mode}  orders={'on' if emit_orders else 'off'}",
        f"# Generated {generated_at} via AiStockAnalysis",
        "#",
        "declare upper;",
        "",
        "# ── Inputs ───────────────────────────────────────────────────",
        f"input fast_length       = {fast_window};",
        f"input slow_length       = {slow_window};",
        f"input breakout_lookback = {breakout_window};",
        f"input atr_length        = {atr_window};",
        f"input stop_atr_mult     = {stop_mult};",
        f"input tp_atr_mult       = {tp_mult};",
        "",
        "# ── Moving Averages ───────────────────────────────────────────",
        "def fastMA = Average(close, fast_length);",
        "def slowMA  = Average(close, slow_length);",
        "",
        "# ── ATR & Breakout Level ──────────────────────────────────────",
        "def atr       = Average(TrueRange(high, close, low), atr_length);",
        "def swingHigh = Highest(high[1], breakout_lookback);",
        "",
        "# ── Entry / Exit Conditions ───────────────────────────────────",
        "def trendUp       = fastMA > slowMA;",
        "def breakoutEntry = close > swingHigh;",
        "def entrySignal   = trendUp and breakoutEntry;",
        "def exitSignal    = close < fastMA or !trendUp;",
        "",
        "# Stop-loss:   entryPrice - atr * stop_atr_mult",
        "# Take-profit: entryPrice + atr * tp_atr_mult",
        "",
        "# ── Signal Plots ──────────────────────────────────────────────",
        "plot BuyArrow = if entrySignal then low * 0.99 else Double.NaN;",
        "BuyArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);",
        "BuyArrow.SetDefaultColor(Color.GREEN);",
        "BuyArrow.SetLineWeight(2);",
        "",
        "plot SellArrow = if exitSignal then high * 1.01 else Double.NaN;",
        "SellArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);",
        "SellArrow.SetDefaultColor(Color.RED);",
        "SellArrow.SetLineWeight(2);",
        "",
        "plot FastMALine = fastMA;",
        "FastMALine.SetDefaultColor(Color.YELLOW);",
        "FastMALine.SetLineWeight(1);",
        "",
        "plot SlowMALine = slowMA;",
        "SlowMALine.SetDefaultColor(Color.CYAN);",
        "SlowMALine.SetLineWeight(1);",
    ]

    if emit_orders:
        lines += [
            "",
            "# ── Orders ────────────────────────────────────────────────────",
            'AddOrder(OrderType.BUY_TO_OPEN,  entrySignal, open[-1], 1, Color.GREEN, Color.GREEN, "Enter Long");',
            'AddOrder(OrderType.SELL_TO_CLOSE, exitSignal,  open[-1], 1, Color.RED,   Color.RED,   "Exit Long");',
        ]

    return "\n".join(lines) + "\n"


def export_thinkscript_scaffold(
    *,
    request: ThinkScriptExportRequest,
    strategy_artifact_path: Path,
    output_path: Path,
) -> ThinkScriptExportResult:
    """Export a ThinkScript script from a strategy artifact (full template rendering)."""

    if not strategy_artifact_path.exists():
        raise FileNotFoundError(
            f"Strategy artifact not found: {strategy_artifact_path}. "
            "Run build-strategy before export-thinkscript."
        )

    payload = json.loads(strategy_artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid strategy artifact format in {strategy_artifact_path}")

    generated_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source = _build_thinkscript_source(
        strategy_payload=payload,
        request=request,
        generated_at=generated_at,
    )
    output_path.write_text(source, encoding="utf-8")

    return ThinkScriptExportResult.generated(
        ticker=request.ticker,
        interval=request.interval,
        export_mode=request.export_mode,
        include_orders=request.include_orders,
        output_path=str(output_path),
        strategy_id=str(payload.get("strategy_id")) if payload.get("strategy_id") else None,
        generated_at=generated_at,
    )
