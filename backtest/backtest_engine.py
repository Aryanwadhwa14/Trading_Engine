import os
import pandas as pd
from datetime import datetime
from strategies.ema_pullback import generate_signal
from upload.tradelogs_update import upload_trade_log_tab, append_strategy_row


def run_backtest(df, config, start_date, end_date):

    balance = config["INITIAL_BALANCE"]
    ticker = config["SINGLE_TICKER"]

    # Optional metadata from config (used in trade log)
    indicators = config.get("INDICATORS", "")

    position = 0
    units = 0
    entry_price = None
    entry_time = None
    stop_loss = None
    take_profit = None
    entry_reason = None
    trade_type = None
    strategy_id = None

    trade_log = []

    for i in range(5, len(df)):

        current_df = df.iloc[:i+1]
        row = df.iloc[i]

        high = row["high"]
        low = row["low"]

        # Check if current candle is the last one of the day
        is_last_candle = False
        if i < len(df) - 1:
            if row.name.date() != df.iloc[i+1].name.date():
                is_last_candle = True
        else:
            is_last_candle = True

        # ENTRY
        if position == 0:

            signal = generate_signal(current_df, config)

            if signal:
                position = 1 if signal["signal"] == "LONG" else -1

                entry_price = signal["entry"]
                stop_loss = signal["stop_loss"]
                take_profit = signal["take_profit"]
                
                # Maximizing profit by using all available capital
                units = max(1, int(balance / entry_price)) if entry_price > 0 else 1

                entry_time = row.name
                entry_reason = signal["reason"]
                trade_type = signal["type"]
                strategy_id = signal["strategy_id"]

        # EXIT LONG
        elif position == 1:

            if low <= stop_loss or high >= take_profit:

                exit_price = stop_loss if low <= stop_loss else take_profit
                raw_pnl = exit_price - entry_price
                pnl = raw_pnl * units

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "LONG", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "SL Hit" if low <= stop_loss else "TP Hit",
                    pnl,
                    units,
                    market=config.get("MARKET", ""), indicators=indicators
                ))

                balance += pnl
                position = 0
            
            elif is_last_candle:
                
                exit_price = row["close"]
                raw_pnl = exit_price - entry_price
                pnl = raw_pnl * units

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "LONG", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "EOD Close",
                    pnl,
                    units,
                    market=config.get("MARKET", ""), indicators=indicators
                ))

                balance += pnl
                position = 0

        # EXIT SHORT
        elif position == -1:

            if high >= stop_loss or low <= take_profit:

                exit_price = stop_loss if high >= stop_loss else take_profit
                raw_pnl = entry_price - exit_price
                pnl = raw_pnl * units

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "SHORT", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "SL Hit" if high >= stop_loss else "TP Hit",
                    pnl,
                    units,
                    market=config.get("MARKET", ""), indicators=indicators
                ))

                balance += pnl
                position = 0
                
            elif is_last_candle:
                
                exit_price = row["close"]
                raw_pnl = entry_price - exit_price
                pnl = raw_pnl * units

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "SHORT", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "EOD Close",
                    pnl,
                    units,
                    market=config.get("MARKET", ""), indicators=indicators
                ))

                balance += pnl
                position = 0

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
               market="", indicators=""):

    raw_pnl_pct = ((exit_price - entry_price) / entry_price * 100) if side == "LONG" else \
                  ((entry_price - exit_price) / entry_price * 100)

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
        "Entry Time": _format_time_pst(entry_time),
        "Entry Price": round(entry_price, 2),
        "Stop Loss": round(sl, 2),
        "Take Profit": round(tp, 2),
        "Exit Time": _format_time_pst(exit_time),
        "Exit Price": round(exit_price, 2),
        "Duration (min)": int((exit_time - entry_time).total_seconds() / 60),
        "Entry Reason": entry_reason,
        "Exit Reason": exit_reason,
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
- Ticker:       {config['SINGLE_TICKER']}
- Timeframe:    {config['TIMEFRAME']}
- Date Range:   {start_date} to {end_date}
- EMA:          EMA {config['EMA_FAST']} / {config['EMA_SLOW']}

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