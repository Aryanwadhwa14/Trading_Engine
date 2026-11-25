import os
import pandas as pd
from datetime import datetime
from strategies.ema_pullback import generate_signal
from upload.tradelogs_update import upload_trade_log_tab, append_strategy_row
from risk.position_sizing import calculate_position_size
from execution.fill_simulator import simulate_entry_fill, simulate_exit_fill
from portfolio.ledger import PortfolioLedger


def run_backtest(df, config, start_date, end_date):

    initial_balance = config["INITIAL_BALANCE"]
    ledger = PortfolioLedger(initial_balance=initial_balance)
    ticker = config["SINGLE_TICKER"]

    # Optional metadata from config (used in trade log)
    indicators = config.get("INDICATORS", "")

    pending_signal = None
    entry_timing = config.get("ENTRY_TIMING", "next_bar")
    risk_pct = config.get("RISK_PERCENT", 0.01)
    commission_rate = float(config.get("COMMISSION_RATE", 0.0))
    slippage_bps = float(config.get("SLIPPAGE_BPS", 0.0))
    stop_target_conflict = config.get("STOP_TARGET_CONFLICT", "stop_first")
    close_at_end = bool(config.get("CLOSE_POSITIONS_AT_END", True))

    trade_log = []

    for i in range(5, len(df)):

        current_df = df.iloc[:i+1]
        row = df.iloc[i]

        bar_open = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        bar_close = float(row["close"])

        # Check if current candle is the last one of the day
        is_last_candle = False
        if i < len(df) - 1:
            if row.name.date() != df.iloc[i+1].name.date():
                is_last_candle = True
        else:
            is_last_candle = True

        # ── 1. Causal Entry from Pending Signal (Next-Bar Execution) ─────────
        if ledger.is_flat and pending_signal is not None and entry_timing == "next_bar":
            side = pending_signal["signal"]
            sl = pending_signal["stop_loss"]
            tp = pending_signal["take_profit"]

            # Preview effective fill price with slippage for accurate sizing
            preview_fill = simulate_entry_fill(
                reference_open=bar_open,
                quantity=1,
                side=side,
                commission_rate=commission_rate,
                slippage_bps=slippage_bps,
            )

            # Reserve cash buffer for entry commission
            effective_cash = ledger.cash / (1.0 + commission_rate) if commission_rate > 0 else ledger.cash

            size_result = calculate_position_size(
                equity=ledger.mark_to_market_equity(),
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
                    symbol=ticker,
                    entry_fill=entry_fill,
                    stop_loss=sl,
                    take_profit=tp,
                    entry_time=row.name,
                    signal_time=pending_signal.get("signal_time", row.name),
                    entry_reason=pending_signal["reason"],
                    trade_type=pending_signal["type"],
                    strategy_id=pending_signal["strategy_id"],
                    risk_budget=size_result.risk_budget,
                    estimated_risk=size_result.estimated_risk,
                )

            pending_signal = None

        # ── 2. Position Exits ────────────────────────────────────────────────
        if not ledger.is_flat:
            pos = ledger.position
            exit_fill = simulate_exit_fill(
                bar_open=bar_open,
                bar_high=high,
                bar_low=low,
                bar_close=bar_close,
                quantity=pos.quantity,
                side=pos.side,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                is_last_candle=is_last_candle,
                commission_rate=commission_rate,
                slippage_bps=slippage_bps,
                stop_target_conflict=stop_target_conflict,
                close_at_end=close_at_end,
            )

            if exit_fill is not None:
                closed = ledger.close_position(exit_fill)
                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], closed.side, pos.trade_type, pos.strategy_id,
                    pos.entry_time, closed.entry_price,
                    pos.stop_loss, pos.take_profit,
                    row.name, closed.exit_price,
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
        if ledger.is_flat and pending_signal is None:

            signal = generate_signal(current_df, config)

            if signal:
                if entry_timing == "next_bar":
                    pending_signal = signal
                else:
                    # Legacy same-bar immediate fill
                    ref_price = signal["entry"]
                    sl = signal["stop_loss"]
                    tp = signal["take_profit"]
                    side = signal["signal"]

                    preview_fill = simulate_entry_fill(
                        reference_open=ref_price,
                        quantity=1,
                        side=side,
                        commission_rate=commission_rate,
                        slippage_bps=slippage_bps,
                    )
                    effective_cash = ledger.cash / (1.0 + commission_rate) if commission_rate > 0 else ledger.cash

                    size_result = calculate_position_size(
                        equity=ledger.mark_to_market_equity(),
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
                            symbol=ticker,
                            entry_fill=entry_fill,
                            stop_loss=sl,
                            take_profit=tp,
                            entry_time=row.name,
                            signal_time=signal.get("signal_time", row.name),
                            entry_reason=signal["reason"],
                            trade_type=signal["type"],
                            strategy_id=signal["strategy_id"],
                            risk_budget=size_result.risk_budget,
                            estimated_risk=size_result.estimated_risk,
                        )

    trades_df = pd.DataFrame(trade_log)

    ticker = config["SINGLE_TICKER"]
    sd_str = str(start_date).split(' ')[0]
    ed_str = str(end_date).split(' ')[0]
    
    base_folder_name = f"{ticker.lower()}_results({sd_str} - {ed_str})"
    
    if "RUN_DIR" in config:
        base_dir = os.path.join(config["RUN_DIR"], base_folder_name)
    else:
        base_dir = os.path.join("results", base_folder_name)
        
    os.makedirs(base_dir, exist_ok=True)

    initial_balance = config["INITIAL_BALANCE"]

    if len(trades_df) > 0:
        if "Strategy No" in trades_df.columns:
            strategies = sorted(trades_df["Strategy No"].dropna().unique())
            for strat in strategies:
                strat_df = trades_df[trades_df["Strategy No"] == strat]
                
                strat_dir = os.path.join(base_dir, f"strategy {int(strat)}")
                os.makedirs(strat_dir, exist_ok=True)

                csv_path  = os.path.join(strat_dir, "trades.csv")
                summ_path = os.path.join(strat_dir, "trades_summary.txt")
                strat_df.to_csv(csv_path, index=False)
                
                summary = _generate_summary(strat_df, initial_balance, config, start_date, end_date, int(strat))
                with open(summ_path, "w") as f:
                    f.write(summary)
                print(summary)

                # ── Google Sheets upload ──────────────────────────────────
                if config.get("UPLOAD_TO_SHEETS", True):
                    tab_name = f"{base_folder_name} - S{int(strat)}"  # Add strategy number to tab name
                    upload_trade_log_tab(strat_df, config, tab_name=tab_name)
                    append_strategy_row(
                        strat_df, config,
                        strategy_id=int(strat),
                        trades_csv_path=csv_path,
                        summary_path=summ_path,
                    )
                # ─────────────────────────────────────────────────────────
        else:
            csv_path  = os.path.join(base_dir, "trades.csv")
            summ_path = os.path.join(base_dir, "trades_summary.txt")
            trades_df.to_csv(csv_path, index=False)
            summary = _generate_summary(trades_df, initial_balance, config, start_date, end_date)
            with open(summ_path, "w") as f:
                f.write(summary)
            print(summary)

            # ── Google Sheets upload ──────────────────────────────────
            if config.get("UPLOAD_TO_SHEETS", True):
                tab_name = base_folder_name
                upload_trade_log_tab(trades_df, config, tab_name=tab_name)
                append_strategy_row(
                    trades_df, config,
                    trades_csv_path=csv_path,
                    summary_path=summ_path,
                )
            # ─────────────────────────────────────────────────────────
    else:
        summary = _generate_summary(trades_df, initial_balance, config, start_date, end_date)
        with open(os.path.join(base_dir, "trades_summary.txt"), "w") as f:
            f.write(summary)
        print(summary)

    return trades_df


# ================= HELPERS ================= #

def _format_time_pst(dt_obj):
    try:
        ts = pd.Timestamp(dt_obj)
        if ts.tz is None:
            ts = ts.tz_localize('America/New_York')
        ts = ts.tz_convert('America/Los_Angeles')
        return f"{ts.strftime('%Y-%m-%d %H:%M:%S')} (PST)"
    except Exception:
        if hasattr(dt_obj, 'strftime'):
            return f"{dt_obj.strftime('%Y-%m-%d %H:%M:%S')} (PST)"
        return f"{dt_obj} (PST)"

def _log_trade(ticker, timeframe, side, trade_type, strategy_id,
               entry_time, entry_price,
               sl, tp,
               exit_time, exit_price,
               entry_reason, exit_reason,
               pnl, units=0,
               market="", indicators="",
               risk_budget=0.0, estimated_risk=0.0,
               signal_time=None,
               gross_pnl=None, fees=0.0, slippage=0.0,
               ambiguous_bar=False):

    raw_pnl_pct = ((exit_price - entry_price) / entry_price * 100) if side == "LONG" else \
                  ((entry_price - exit_price) / entry_price * 100)

    sig_time_str = _format_time_pst(signal_time if signal_time is not None else entry_time)
    g_pnl = pnl if gross_pnl is None else gross_pnl

    return {
        "Trade Date": entry_time.date(),
        "Ticker": ticker,
        "Market": market,
        "Timeframe": timeframe,
        "Side": side,
        "Trade Type": trade_type.upper(),
        "Strategy No": strategy_id,
        "Indicators": indicators,
        "Units": units,
        "Risk Budget ($)": round(risk_budget, 2),
        "Est Risk ($)": round(estimated_risk, 2),
        "Signal Time": sig_time_str,
        "Entry Time": _format_time_pst(entry_time),
        "Entry Price": round(entry_price, 4),
        "Stop Loss": round(sl, 2),
        "Take Profit": round(tp, 2),
        "Exit Time": _format_time_pst(exit_time),
        "Exit Price": round(exit_price, 4),
        "Duration (min)": int((exit_time - entry_time).total_seconds() / 60),
        "Entry Reason": entry_reason,
        "Exit Reason": exit_reason,
        "Ambiguous Bar": ambiguous_bar,
        "Gross PnL ($)": round(g_pnl, 2),
        "Fees ($)": round(fees, 2),
        "Slippage ($)": round(slippage, 2),
        "PnL ($)": round(pnl, 2),
        "Return %": round(raw_pnl_pct, 4),
        "Result": "WIN" if pnl > 0 else "LOSS"
    }


def _generate_summary(df, initial_balance, config, start_date, end_date, strategy_id=None):

    if len(df) == 0:
        return "No trades."

    wins = len(df[df["Result"] == "WIN"])
    losses = len(df[df["Result"] == "LOSS"])

    win_rate = (wins / len(df)) * 100 if len(df) > 0 else 0
    net_profit = df["PnL ($)"].sum() if len(df) > 0 else 0

    final_bal = initial_balance + net_profit

    avg_win = df[df["Result"] == "WIN"]["PnL ($)"].mean() if wins else 0
    avg_loss = df[df["Result"] == "LOSS"]["PnL ($)"].mean() if losses else 0
    
    avg_units = df["Units"].mean() if "Units" in df.columns and len(df) > 0 else 0

    max_win = df["PnL ($)"].max() if len(df) > 0 else 0
    max_loss = df["PnL ($)"].min() if len(df) > 0 else 0

    header = f"{config['SINGLE_TICKER']} BACKTEST RESULTS"
    if strategy_id is not None:
        header += f" -> Strategy {strategy_id}"

    return f"""
{header}
============================================================

Configuration:
- Ticker:       {config.get('SINGLE_TICKER', '')}
- Timeframe:    {config.get('TIMEFRAME', '')}
- Date Range:   {start_date} to {end_date}
- EMA:          EMA {config.get('EMA_FAST', '')} / {config.get('EMA_SLOW', '')}

Performance:
- Total Trades: {len(df)}
- Number of Units:    {avg_units:.0f}
- Wins:         {wins}
- Losses:       {losses}
- Win Rate:     {win_rate:.1f}%
- Net Profit:   ${net_profit:,.2f}
- Final Bal:    ${final_bal:,.2f}
- Avg Win:      ${avg_win:,.2f}
- Avg Loss:     ${avg_loss:,.2f}
- Max Win:      ${max_win:,.2f}
- Max Loss:     ${max_loss:,.2f}
"""


def _create_results_folder():
    folder = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder, exist_ok=True)
    return folder