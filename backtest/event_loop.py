"""
backtest/event_loop.py
──────────────────────
Shared chronological multi-asset portfolio backtest engine.

Replaces independent full-balance per-ticker runs with one unified portfolio:
- Chronological event stream across all symbols without forward-filling missing bars.
- Shared cash, buying power, risk budget, and gross exposure.
- Deterministic alphabetical ordering for same-timestamp events.
- Enforces max open positions, gross exposure, per-symbol exposure, and daily loss halts.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from backtest.backtest_engine import _log_trade
from backtest.performance import (
    build_run_metadata,
    compute_performance_metrics,
    compute_strategy_attribution,
    format_portfolio_report,
    save_run_metadata,
)
from execution.fill_simulator import simulate_entry_fill, simulate_exit_fill
from portfolio.ledger import PortfolioLedger
from risk.portfolio_limits import PortfolioRiskConfig, check_portfolio_limits
from risk.position_sizing import calculate_position_size
from strategies.ema_pullback import generate_signal


def _normalize_timezone(df: pd.DataFrame, target_tz: str = "UTC") -> pd.DataFrame:
    """Align DataFrame index to a common timezone for multi-asset chronological sorting."""
    out = df.copy()
    if out.index.tz is None:
        out.index = out.index.tz_localize(target_tz)
    else:
        out.index = out.index.tz_convert(target_tz)
    return out


def run_portfolio_backtest(
    data_by_symbol: dict[str, pd.DataFrame],
    config: dict[str, Any],
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Run a shared multi-asset chronological portfolio backtest.

    Parameters
    ----------
    data_by_symbol : dict[str, pd.DataFrame]
        Mapping of symbol -> validated OHLCV DataFrame with indicator columns.
    config : dict
        Engine, strategy, cost, and portfolio risk parameters.
    start_date, end_date : str
        Backtest date range strings for reporting.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame, dict]
        (trades_df, enriched_equity_df, metadata_dict)
    """
    if not data_by_symbol:
        raise ValueError("data_by_symbol must contain at least one symbol DataFrame.")

    initial_balance = float(config["INITIAL_BALANCE"])
    ledger = PortfolioLedger(initial_balance=initial_balance)
    indicators = config.get("INDICATORS", "")

    entry_timing = config.get("ENTRY_TIMING", "next_bar")
    risk_pct = float(config.get("RISK_PERCENT", 0.01))
    commission_rate = float(config.get("COMMISSION_RATE", 0.0))
    slippage_bps = float(config.get("SLIPPAGE_BPS", 0.0))
    stop_target_conflict = config.get("STOP_TARGET_CONFLICT", "stop_first")
    close_at_end = bool(config.get("CLOSE_POSITIONS_AT_END", True))

    limits = PortfolioRiskConfig(
        max_open_positions=int(config.get("MAX_OPEN_POSITIONS", 3)),
        max_gross_exposure=float(config.get("MAX_GROSS_EXPOSURE", 0.80)),
        max_symbol_exposure=float(config.get("MAX_SYMBOL_EXPOSURE", 0.50)),
        max_daily_loss_pct=float(config.get("MAX_DAILY_LOSS", 0.02)),
        max_drawdown_pct=config.get("MAX_DRAWDOWN_PCT"),
    )

    # Sort symbols deterministically and align timezones
    sorted_symbols = sorted(data_by_symbol.keys())
    aligned_data: dict[str, pd.DataFrame] = {}
    ts_to_pos: dict[str, dict[pd.Timestamp, int]] = {}
    last_candle_flags: dict[str, list[bool]] = {}

    for sym in sorted_symbols:
        df_sym = _normalize_timezone(data_by_symbol[sym])
        aligned_data[sym] = df_sym
        ts_to_pos[sym] = {ts: idx for idx, ts in enumerate(df_sym.index)}

        # Precompute EOD / final-bar flags per symbol
        n = len(df_sym)
        flags = [False] * n
        for idx in range(n):
            if idx == n - 1:
                flags[idx] = True
            elif df_sym.index[idx].date() != df_sym.index[idx + 1].date():
                flags[idx] = True
        last_candle_flags[sym] = flags

    all_timestamps = sorted(set().union(*(df.index for df in aligned_data.values())))

    last_known_close: dict[str, float] = {}
    pending_signals: dict[str, Any] = {}
    trade_log: list[dict[str, Any]] = []
    equity_records: list[dict[str, Any]] = []

    current_date = None
    day_start_equity = initial_balance
    peak_equity = initial_balance

    for ts in all_timestamps:
        symbols_at_ts = [sym for sym in sorted_symbols if ts in ts_to_pos[sym]]

        # Update latest known marks for symbols active at this timestamp
        for sym in symbols_at_ts:
            pos_idx = ts_to_pos[sym][ts]
            last_known_close[sym] = float(aligned_data[sym].iloc[pos_idx]["close"])

        # Track daily equity baseline for daily loss halt
        bar_date = ts.date()
        if current_date is None or bar_date != current_date:
            day_start_equity = ledger.mark_to_market_equity(last_known_close)
            current_date = bar_date

        # ── 1. Causal Entries from Pending Signals (Next-Bar Execution) ──────
        if entry_timing == "next_bar":
            for sym in symbols_at_ts:
                if sym not in pending_signals:
                    continue

                sig = pending_signals.pop(sym)
                if ledger.has_position(sym):
                    continue

                pos_idx = ts_to_pos[sym][ts]
                row = aligned_data[sym].iloc[pos_idx]
                bar_open = float(row["open"])
                side = sig["signal"]
                sl = sig["stop_loss"]
                tp = sig["take_profit"]

                curr_equity = ledger.mark_to_market_equity(last_known_close)
                peak_equity = max(peak_equity, curr_equity)
                curr_gross = ledger.gross_exposure(last_known_close)

                decision = check_portfolio_limits(
                    symbol=sym,
                    current_equity=curr_equity,
                    day_start_equity=day_start_equity,
                    peak_equity=peak_equity,
                    open_positions_count=ledger.open_position_count,
                    has_symbol_position=ledger.has_position(sym),
                    current_gross_exposure=curr_gross,
                    limits=limits,
                )
                if not decision.is_approved:
                    continue

                preview_fill = simulate_entry_fill(
                    reference_open=bar_open,
                    quantity=1,
                    side=side,
                    commission_rate=commission_rate,
                    slippage_bps=slippage_bps,
                )

                # For cash-equity long, cap by both available cash and portfolio exposure headroom
                raw_cash_cap = min(ledger.cash, decision.max_allowed_notional) if side == "LONG" else min(curr_equity, decision.max_allowed_notional)
                effective_cash = raw_cash_cap / (1.0 + commission_rate) if commission_rate > 0 else raw_cash_cap

                size_result = calculate_position_size(
                    equity=curr_equity,
                    entry_price=preview_fill.fill_price,
                    stop_price=sl,
                    risk_percent=risk_pct,
                    cash_available=effective_cash,
                    side=side,
                )

                if size_result.is_approved and size_result.quantity > 0:
                    entry_fill = simulate_entry_fill(
                        reference_open=bar_open,
                        quantity=size_result.quantity,
                        side=side,
                        commission_rate=commission_rate,
                        slippage_bps=slippage_bps,
                    )
                    ledger.open_position(
                        symbol=sym,
                        entry_fill=entry_fill,
                        stop_loss=sl,
                        take_profit=tp,
                        entry_time=ts,
                        signal_time=sig.get("signal_time", ts),
                        entry_reason=sig["reason"],
                        trade_type=sig["type"],
                        strategy_id=sig["strategy_id"],
                        risk_budget=size_result.risk_budget,
                        estimated_risk=size_result.estimated_risk,
                    )

        # ── 2. Position Exits ────────────────────────────────────────────────
        for sym in symbols_at_ts:
            if not ledger.has_position(sym):
                continue

            pos_idx = ts_to_pos[sym][ts]
            row = aligned_data[sym].iloc[pos_idx]
            pos = ledger.positions[sym]

            exit_fill = simulate_exit_fill(
                bar_open=float(row["open"]),
                bar_high=float(row["high"]),
                bar_low=float(row["low"]),
                bar_close=float(row["close"]),
                quantity=pos.quantity,
                side=pos.side,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                is_last_candle=last_candle_flags[sym][pos_idx],
                commission_rate=commission_rate,
                slippage_bps=slippage_bps,
                stop_target_conflict=stop_target_conflict,
                close_at_end=close_at_end,
            )

            if exit_fill is not None:
                closed = ledger.close_position(exit_fill, symbol=sym)
                trade_log.append(_log_trade(
                    sym, config.get("TIMEFRAME", "5m"), closed.side, pos.trade_type, pos.strategy_id,
                    pos.entry_time, closed.entry_price,
                    pos.stop_loss, pos.take_profit,
                    ts, closed.exit_price,
                    pos.entry_reason, closed.exit_reason,
                    closed.net_pnl,
                    closed.quantity,
                    market=config.get("MARKET", ""), indicators=indicators,
                    risk_budget=pos.risk_budget, estimated_risk=pos.estimated_risk,
                    signal_time=pos.signal_time,
                    gross_pnl=closed.gross_pnl,
                    fees=closed.commission_cost,
                    slippage=closed.slippage_cost,
                    ambiguous_bar=closed.ambiguous_bar,
                ))

        # ── 3. Strategy Evaluation at Completed Bar Close ────────────────────
        for sym in symbols_at_ts:
            if ledger.has_position(sym) or sym in pending_signals:
                continue

            pos_idx = ts_to_pos[sym][ts]
            if pos_idx < 5:
                continue

            current_df = aligned_data[sym].iloc[:pos_idx + 1]
            sym_cfg = config.copy()
            sym_cfg["SINGLE_TICKER"] = sym
            signal = generate_signal(current_df, sym_cfg)

            if signal:
                if entry_timing == "next_bar":
                    pending_signals[sym] = signal
                else:
                    # Legacy same-bar immediate fill
                    ref_price = signal["entry"]
                    side = signal["signal"]
                    sl = signal["stop_loss"]
                    tp = signal["take_profit"]

                    curr_equity = ledger.mark_to_market_equity(last_known_close)
                    peak_equity = max(peak_equity, curr_equity)
                    curr_gross = ledger.gross_exposure(last_known_close)

                    decision = check_portfolio_limits(
                        symbol=sym,
                        current_equity=curr_equity,
                        day_start_equity=day_start_equity,
                        peak_equity=peak_equity,
                        open_positions_count=ledger.open_position_count,
                        has_symbol_position=ledger.has_position(sym),
                        current_gross_exposure=curr_gross,
                        limits=limits,
                    )
                    if not decision.is_approved:
                        continue

                    preview_fill = simulate_entry_fill(
                        reference_open=ref_price,
                        quantity=1,
                        side=side,
                        commission_rate=commission_rate,
                        slippage_bps=slippage_bps,
                    )
                    raw_cash_cap = min(ledger.cash, decision.max_allowed_notional) if side == "LONG" else min(curr_equity, decision.max_allowed_notional)
                    effective_cash = raw_cash_cap / (1.0 + commission_rate) if commission_rate > 0 else raw_cash_cap

                    size_result = calculate_position_size(
                        equity=curr_equity,
                        entry_price=preview_fill.fill_price,
                        stop_price=sl,
                        risk_percent=risk_pct,
                        cash_available=effective_cash,
                        side=side,
                    )
                    if size_result.is_approved and size_result.quantity > 0:
                        entry_fill = simulate_entry_fill(
                            reference_open=ref_price,
                            quantity=size_result.quantity,
                            side=side,
                            commission_rate=commission_rate,
                            slippage_bps=slippage_bps,
                        )
                        ledger.open_position(
                            symbol=sym,
                            entry_fill=entry_fill,
                            stop_loss=sl,
                            take_profit=tp,
                            entry_time=ts,
                            signal_time=signal.get("signal_time", ts),
                            entry_reason=signal["reason"],
                            trade_type=signal["type"],
                            strategy_id=signal["strategy_id"],
                            risk_budget=size_result.risk_budget,
                            estimated_risk=size_result.estimated_risk,
                        )

        # ── 4. Record Portfolio Equity Curve ─────────────────────────────────
        curr_eq = ledger.mark_to_market_equity(last_known_close)
        peak_equity = max(peak_equity, curr_eq)
        curr_gross = ledger.gross_exposure(last_known_close)
        equity_records.append({
            "timestamp": ts,
            "equity": curr_eq,
            "cash": ledger.cash,
            "open_positions": ledger.open_position_count,
            "in_market": 0 if ledger.is_flat else 1,
            "position_value": curr_gross,
        })

    trades_df = pd.DataFrame(trade_log)
    equity_df = pd.DataFrame(equity_records)

    sd_str = str(start_date).split(" ")[0]
    ed_str = str(end_date).split(" ")[0]
    label = f"portfolio_{len(sorted_symbols)}tickers({sd_str} - {ed_str})"

    if "RUN_DIR" in config:
        base_dir = os.path.join(config["RUN_DIR"], label)
    else:
        base_dir = os.path.join("results", label)
    os.makedirs(base_dir, exist_ok=True)

    if len(trades_df) > 0:
        trades_df.to_csv(os.path.join(base_dir, "trades.csv"), index=False)

    metrics, enriched_equity_df = compute_performance_metrics(
        equity_df=equity_df,
        trades_df=trades_df,
        initial_balance=initial_balance,
        timeframe=config.get("TIMEFRAME", "5m"),
        benchmark_close=None,
        split_label=config.get("SPLIT_LABEL", "in_sample"),
    )
    attribution = compute_strategy_attribution(trades_df)

    enriched_equity_df.to_csv(os.path.join(base_dir, "equity_curve.csv"), index=False)

    report = format_portfolio_report(
        metrics=metrics,
        attribution=attribution,
        ticker=f"PORTFOLIO ({', '.join(sorted_symbols)})",
        start_date=str(start_date),
        end_date=str(end_date),
    )
    with open(os.path.join(base_dir, "portfolio_summary.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)

    meta_cfg = config.copy()
    meta_cfg["SINGLE_TICKER"] = ",".join(sorted_symbols)
    metadata = build_run_metadata(
        config=meta_cfg,
        start_date=str(start_date),
        end_date=str(end_date),
        metrics=metrics,
        attribution=attribution,
    )
    save_run_metadata(metadata, os.path.join(base_dir, "run_metadata.json"))

    return trades_df, enriched_equity_df, metadata

