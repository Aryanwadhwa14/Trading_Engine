"""
backtest/performance.py
───────────────────────
Quantitative performance analytics, drawdown tracking, benchmark comparison,
cost attribution, and reproducible run metadata generation.

Assumptions & Conventions:
- Annualization uses US regular trading hours (390 min/day * 252 trading days/year).
- Sharpe ratio uses 0.0% risk-free rate over bar-level equity returns.
- Metrics that are statistically meaningless (e.g. Sharpe with 0 variance or < 2 bars,
  profit factor with 0 losses) are explicitly returned as None ('N/A' in reports).
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


_BARS_PER_YEAR_MAP = {
    "1m": 390 * 252,
    "2m": 195 * 252,
    "5m": 78 * 252,
    "15m": 26 * 252,
    "30m": 13 * 252,
    "1h": 6.5 * 252,
    "60m": 6.5 * 252,
    "1d": 252,
}


def get_bars_per_year(timeframe: str) -> float:
    """Return annualization factor (bars per year) for a given timeframe."""
    tf = timeframe.strip().lower()
    if tf in _BARS_PER_YEAR_MAP:
        return float(_BARS_PER_YEAR_MAP[tf])
    if tf.endswith("m"):
        mins = int(tf[:-1])
        return (390.0 / max(1, mins)) * 252.0
    if tf.endswith("h"):
        hrs = int(tf[:-1])
        return (6.5 / max(1, hrs)) * 252.0
    return 252.0


@dataclass(frozen=True)
class PerformanceMetrics:
    """Complete portfolio-level performance summary."""
    initial_balance: float
    final_equity: float
    net_profit: float
    net_return_pct: float
    benchmark_return_pct: float | None
    excess_return_pct: float | None
    max_drawdown_dollar: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    annualized_volatility_pct: float | None
    sharpe_ratio: float | None
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float | None
    avg_win_dollar: float | None
    avg_loss_dollar: float | None
    expectancy_dollar: float | None
    profit_factor: float | None
    gross_profit_dollar: float
    total_fees_dollar: float
    total_slippage_dollar: float
    turnover_ratio: float
    time_in_market_pct: float
    avg_exposure_pct: float
    timeframe: str
    annualization_bars_per_year: float
    split_label: str = "in_sample"


def compute_drawdown_series(equity_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add `peak_equity`, `drawdown_dollar`, and `drawdown_pct` columns to an equity DataFrame.
    """
    out = equity_df.copy()
    if out.empty:
        out["peak_equity"] = pd.Series(dtype=float)
        out["drawdown_dollar"] = pd.Series(dtype=float)
        out["drawdown_pct"] = pd.Series(dtype=float)
        return out

    out["peak_equity"] = out["equity"].cummax()
    out["drawdown_dollar"] = out["equity"] - out["peak_equity"]
    out["drawdown_pct"] = np.where(
        out["peak_equity"] > 0,
        (out["equity"] / out["peak_equity"] - 1.0) * 100.0,
        0.0,
    )
    return out


def _max_drawdown_duration(equity_series: pd.Series, peak_series: pd.Series) -> int:
    """Compute longest contiguous run of bars where equity < peak_equity."""
    if equity_series.empty:
        return 0
    underwater = equity_series < peak_series
    max_dur = 0
    curr_dur = 0
    for is_uw in underwater:
        if is_uw:
            curr_dur += 1
            if curr_dur > max_dur:
                max_dur = curr_dur
        else:
            curr_dur = 0
    return max_dur


def compute_performance_metrics(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial_balance: float,
    timeframe: str = "5m",
    benchmark_close: pd.Series | None = None,
    split_label: str = "in_sample",
) -> tuple[PerformanceMetrics, pd.DataFrame]:
    """
    Compute reconciled performance metrics from the bar-by-bar equity curve and trade log.
    Returns (PerformanceMetrics, enriched_equity_df).
    """
    dd_df = compute_drawdown_series(equity_df)
    bars_per_year = get_bars_per_year(timeframe)

    if dd_df.empty:
        final_equity = float(initial_balance)
        max_dd_dollar = 0.0
        max_dd_pct = 0.0
        max_dd_dur = 0
        time_in_market_pct = 0.0
        avg_exposure_pct = 0.0
    else:
        final_equity = float(dd_df["equity"].iloc[-1])
        max_dd_dollar = float(dd_df["drawdown_dollar"].min())
        max_dd_pct = float(dd_df["drawdown_pct"].min())
        max_dd_dur = _max_drawdown_duration(dd_df["equity"], dd_df["peak_equity"])
        time_in_market_pct = float(dd_df["in_market"].mean() * 100.0) if "in_market" in dd_df else 0.0
        if "position_value" in dd_df:
            exp_series = np.where(dd_df["equity"] > 0, dd_df["position_value"] / dd_df["equity"], 0.0)
            avg_exposure_pct = float(np.mean(exp_series) * 100.0)
        else:
            avg_exposure_pct = 0.0

    net_profit = final_equity - initial_balance
    net_return_pct = (net_profit / initial_balance) * 100.0 if initial_balance > 0 else 0.0

    # Benchmark comparison over matching bars
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    if benchmark_close is not None and len(benchmark_close) >= 2:
        b_start = float(benchmark_close.iloc[0])
        b_end = float(benchmark_close.iloc[-1])
        if b_start > 0:
            benchmark_return_pct = ((b_end / b_start) - 1.0) * 100.0
            excess_return_pct = net_return_pct - benchmark_return_pct

    # Trade statistics
    total_trades = len(trades_df) if trades_df is not None else 0
    if total_trades > 0:
        wins_df = trades_df[trades_df["Result"] == "WIN"]
        losses_df = trades_df[trades_df["Result"] == "LOSS"]
        wins = len(wins_df)
        losses = len(losses_df)
        win_rate_pct = (wins / total_trades) * 100.0
        avg_win_dollar = float(wins_df["PnL ($)"].mean()) if wins > 0 else None
        avg_loss_dollar = float(losses_df["PnL ($)"].mean()) if losses > 0 else None

        sum_wins = float(wins_df["PnL ($)"].sum()) if wins > 0 else 0.0
        sum_losses_abs = abs(float(losses_df["PnL ($)"].sum())) if losses > 0 else 0.0
        profit_factor = (sum_wins / sum_losses_abs) if (wins > 0 and sum_losses_abs > 0) else None

        gross_profit = float(trades_df["Gross PnL ($)"].sum()) if "Gross PnL ($)" in trades_df else float(trades_df["PnL ($)"].sum())
        total_fees = float(trades_df["Fees ($)"].sum()) if "Fees ($)" in trades_df else 0.0
        total_slippage = float(trades_df["Slippage ($)"].sum()) if "Slippage ($)" in trades_df else 0.0
        net_trades_pnl = float(trades_df["PnL ($)"].sum())
        expectancy_dollar = net_trades_pnl / total_trades

        entry_notional = (trades_df["Entry Price"] * trades_df["Units"]).sum()
        exit_notional = (trades_df["Exit Price"] * trades_df["Units"]).sum()
        turnover_ratio = float((entry_notional + exit_notional) / initial_balance) if initial_balance > 0 else 0.0
    else:
        wins = 0
        losses = 0
        win_rate_pct = None
        avg_win_dollar = None
        avg_loss_dollar = None
        profit_factor = None
        gross_profit = 0.0
        total_fees = 0.0
        total_slippage = 0.0
        expectancy_dollar = None
        turnover_ratio = 0.0

    # Volatility & Sharpe
    annualized_volatility_pct: float | None = None
    sharpe_ratio: float | None = None
    if not dd_df.empty and len(dd_df) >= 2 and total_trades > 0:
        returns = dd_df["equity"].pct_change().dropna()
        std_ret = float(returns.std(ddof=1)) if len(returns) >= 2 else 0.0
        if std_ret > 1e-12:
            annualized_volatility_pct = std_ret * math.sqrt(bars_per_year) * 100.0
            sharpe_ratio = (float(returns.mean()) / std_ret) * math.sqrt(bars_per_year)

    metrics = PerformanceMetrics(
        initial_balance=round(initial_balance, 2),
        final_equity=round(final_equity, 2),
        net_profit=round(net_profit, 2),
        net_return_pct=round(net_return_pct, 4),
        benchmark_return_pct=round(benchmark_return_pct, 4) if benchmark_return_pct is not None else None,
        excess_return_pct=round(excess_return_pct, 4) if excess_return_pct is not None else None,
        max_drawdown_dollar=round(max_dd_dollar, 2),
        max_drawdown_pct=round(max_dd_pct, 4),
        max_drawdown_duration_bars=max_dd_dur,
        annualized_volatility_pct=round(annualized_volatility_pct, 2) if annualized_volatility_pct is not None else None,
        sharpe_ratio=round(sharpe_ratio, 3) if sharpe_ratio is not None else None,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate_pct=round(win_rate_pct, 2) if win_rate_pct is not None else None,
        avg_win_dollar=round(avg_win_dollar, 2) if avg_win_dollar is not None else None,
        avg_loss_dollar=round(avg_loss_dollar, 2) if avg_loss_dollar is not None else None,
        expectancy_dollar=round(expectancy_dollar, 2) if expectancy_dollar is not None else None,
        profit_factor=round(profit_factor, 3) if profit_factor is not None else None,
        gross_profit_dollar=round(gross_profit, 2),
        total_fees_dollar=round(total_fees, 2),
        total_slippage_dollar=round(total_slippage, 2),
        turnover_ratio=round(turnover_ratio, 2),
        time_in_market_pct=round(time_in_market_pct, 2),
        avg_exposure_pct=round(avg_exposure_pct, 2),
        timeframe=timeframe,
        annualization_bars_per_year=bars_per_year,
        split_label=split_label,
    )
    return metrics, dd_df


def compute_strategy_attribution(trades_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute per-strategy breakdown from closed trades."""
    if trades_df is None or trades_df.empty or "Strategy No" not in trades_df.columns:
        return []

    rows = []
    for strat_id in sorted(trades_df["Strategy No"].dropna().unique()):
        sub = trades_df[trades_df["Strategy No"] == strat_id]
        n = len(sub)
        wins = int((sub["Result"] == "WIN").sum())
        wr = round((wins / n) * 100.0, 2) if n > 0 else 0.0
        gross = round(float(sub["Gross PnL ($)"].sum()), 2) if "Gross PnL ($)" in sub else 0.0
        fees = round(float(sub["Fees ($)"].sum()), 2) if "Fees ($)" in sub else 0.0
        slip = round(float(sub["Slippage ($)"].sum()), 2) if "Slippage ($)" in sub else 0.0
        net = round(float(sub["PnL ($)"].sum()), 2)
        rows.append({
            "strategy_id": int(strat_id),
            "trades": n,
            "win_rate_pct": wr,
            "gross_pnl": gross,
            "fees": fees,
            "slippage": slip,
            "net_pnl": net,
            "expectancy": round(net / n, 2) if n > 0 else 0.0,
        })
    return rows


def format_portfolio_report(
    metrics: PerformanceMetrics,
    attribution: list[dict[str, Any]],
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """Format a human-readable portfolio performance & attribution report."""
    def _fmt(val: Any, suffix: str = "") -> str:
        return "N/A" if val is None else f"{val}{suffix}"

    lines = [
        f"{ticker} PORTFOLIO PERFORMANCE REPORT ({metrics.split_label.upper()})",
        "=" * 64,
        f"Period:        {start_date} to {end_date} | Timeframe: {metrics.timeframe}",
        f"Assumptions:   {metrics.annualization_bars_per_year:.0f} bars/yr | Risk-free rate: 0.0%",
        "",
        "Returns & Benchmark:",
        f"- Initial Balance:    ${metrics.initial_balance:,.2f}",
        f"- Final Equity:       ${metrics.final_equity:,.2f}",
        f"- Net Profit:         ${metrics.net_profit:,.2f} ({metrics.net_return_pct:+.2f}%)",
        f"- Buy & Hold Bench:   {_fmt(metrics.benchmark_return_pct, '%')}",
        f"- Excess Return:      {_fmt(metrics.excess_return_pct, '%')}",
        "",
        "Risk & Drawdown:",
        f"- Max Drawdown:       ${metrics.max_drawdown_dollar:,.2f} ({metrics.max_drawdown_pct:.2f}%)",
        f"- Max DD Duration:    {metrics.max_drawdown_duration_bars} bars",
        f"- Annualized Vol:     {_fmt(metrics.annualized_volatility_pct, '%')}",
        f"- Sharpe Ratio:       {_fmt(metrics.sharpe_ratio)}",
        "",
        "Trade Quality & Costs:",
        f"- Total Trades:       {metrics.total_trades} (W: {metrics.wins} / L: {metrics.losses})",
        f"- Win Rate:           {_fmt(metrics.win_rate_pct, '%')}",
        f"- Profit Factor:      {_fmt(metrics.profit_factor)}",
        f"- Expectancy/Trade:   {_fmt(metrics.expectancy_dollar, ' $')}",
        f"- Avg Win / Loss:     {_fmt(metrics.avg_win_dollar)} / {_fmt(metrics.avg_loss_dollar)}",
        f"- Gross P&L:          ${metrics.gross_profit_dollar:,.2f}",
        f"- Total Fees:         ${metrics.total_fees_dollar:,.2f}",
        f"- Total Slippage:     ${metrics.total_slippage_dollar:,.2f}",
        f"- Turnover Ratio:     {metrics.turnover_ratio:.2f}x",
        f"- Time in Market:     {metrics.time_in_market_pct:.2f}% (Avg Exposure: {metrics.avg_exposure_pct:.2f}%)",
    ]

    if attribution:
        lines.append("")
        lines.append("Per-Strategy Attribution:")
        for row in attribution:
            lines.append(
                f"- Strategy {row['strategy_id']}: {row['trades']} trades | "
                f"WR {row['win_rate_pct']:.1f}% | Gross ${row['gross_pnl']:,.2f} | "
                f"Costs ${row['fees'] + row['slippage']:,.2f} | Net ${row['net_pnl']:,.2f}"
            )

    return "\n".join(lines) + "\n"


def _get_git_revision() -> str | None:
    """Safely query current git commit hash if available."""
    try:
        out = subprocess.check_output(
            ["git", "-c", "safe.directory=*", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return out.strip()
    except Exception:
        return None


def build_run_metadata(
    config: dict[str, Any],
    start_date: str,
    end_date: str,
    metrics: PerformanceMetrics,
    attribution: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build reproducible JSON-serializable run metadata."""
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": _get_git_revision(),
        "ticker": config.get("SINGLE_TICKER"),
        "timeframe": config.get("TIMEFRAME"),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "split_label": metrics.split_label,
        "parameters": {
            "initial_balance": config.get("INITIAL_BALANCE"),
            "risk_percent": config.get("RISK_PERCENT"),
            "ema_fast": config.get("EMA_FAST"),
            "ema_slow": config.get("EMA_SLOW"),
            "commission_rate": config.get("COMMISSION_RATE", 0.0),
            "slippage_bps": config.get("SLIPPAGE_BPS", 0.0),
            "entry_timing": config.get("ENTRY_TIMING", "next_bar"),
            "stop_target_conflict": config.get("STOP_TARGET_CONFLICT", "stop_first"),
            "close_positions_at_end": config.get("CLOSE_POSITIONS_AT_END", True),
        },
        "metrics": asdict(metrics),
        "strategy_attribution": attribution,
    }


def save_run_metadata(metadata: dict[str, Any], filepath: str) -> None:
    """Write run metadata JSON to disk."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

