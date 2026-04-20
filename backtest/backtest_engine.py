import os
import pandas as pd
from datetime import datetime
from strategies.ema_pullback import generate_signal


def run_backtest(df, config, start_date, end_date):

    balance = config.get("INITIAL_BALANCE", 10000)
    ticker = config["SINGLE_TICKER"]

    position = 0
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

        # ENTRY
        if position == 0:

            signal = generate_signal(current_df)

            if signal:
                position = 1 if signal["signal"] == "LONG" else -1

                entry_price = signal["entry"]
                stop_loss = signal["stop_loss"]
                take_profit = signal["take_profit"]

                entry_time = row.name
                entry_reason = signal["reason"]
                trade_type = signal["type"]
                strategy_id = signal["strategy_id"]

        # EXIT LONG
        elif position == 1:

            if low <= stop_loss or high >= take_profit:

                exit_price = stop_loss if low <= stop_loss else take_profit
                pnl = exit_price - entry_price

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "LONG", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "SL Hit" if low <= stop_loss else "TP Hit",
                    pnl
                ))

                balance += pnl
                position = 0

        # EXIT SHORT
        elif position == -1:

            if high >= stop_loss or low <= take_profit:

                exit_price = stop_loss if high >= stop_loss else take_profit
                pnl = entry_price - exit_price

                trade_log.append(_log_trade(
                    ticker, config["TIMEFRAME"], "SHORT", trade_type, strategy_id,
                    entry_time, entry_price,
                    stop_loss, take_profit,
                    row.name, exit_price,
                    entry_reason,
                    "SL Hit" if high >= stop_loss else "TP Hit",
                    pnl
                ))

                balance += pnl
                position = 0

    trades_df = pd.DataFrame(trade_log)

    results_dir = _create_results_folder()

    if len(trades_df) > 0:
        trades_df.to_csv(os.path.join(results_dir, "trade_log.csv"), index=False)

    summary = _generate_summary(trades_df, balance, config, start_date, end_date)

    with open(os.path.join(results_dir, "summary.txt"), "w") as f:
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
               pnl):

    return {
        "Trade Date": entry_time.date(),
        "Ticker": ticker,
        "Timeframe": timeframe,
        "Side": side,
        "Trade Type": trade_type.upper(),
        "Strategy No": strategy_id,
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
        "Result": "WIN" if pnl > 0 else "LOSS"
    }


def _generate_summary(df, balance, config, start_date, end_date):

    if len(df) == 0:
        return "No trades."

    wins = len(df[df["Result"] == "WIN"])
    losses = len(df[df["Result"] == "LOSS"])

    win_rate = (wins / len(df)) * 100
    net_profit = df["PnL ($)"].sum()

    avg_win = df[df["Result"] == "WIN"]["PnL ($)"].mean() if wins else 0
    avg_loss = df[df["Result"] == "LOSS"]["PnL ($)"].mean() if losses else 0

    max_win = df["PnL ($)"].max()
    max_loss = df["PnL ($)"].min()

    strategy_metrics = ""
    if "Strategy No" in df.columns:
        strategy_metrics = "\nStrategy Breakdown:\n"
        strategy_metrics += "-" * 30 + "\n"
        for strat in sorted(df["Strategy No"].unique()):
            strat_df = df[df["Strategy No"] == strat]
            s_trades = len(strat_df)
            s_wins = len(strat_df[strat_df["Result"] == "WIN"])
            s_losses = len(strat_df[strat_df["Result"] == "LOSS"])
            s_win_rate = (s_wins / s_trades) * 100 if s_trades > 0 else 0
            s_pnl = strat_df["PnL ($)"].sum()
            
            side_val = strat_df["Side"].iloc[0].capitalize() if "Side" in strat_df.columns else "Unknown"
            type_val = strat_df["Trade Type"].iloc[0].capitalize() if "Trade Type" in strat_df.columns else "Unknown"
            
            strategy_metrics += f"- Strategy {strat} ({side_val} -> {type_val}):\n"
            strategy_metrics += f"    Trades: {s_trades} | Wins: {s_wins} | Losses: {s_losses} | Win Rate: {s_win_rate:.1f}%\n"
            strategy_metrics += f"    Net PnL: ${s_pnl:,.2f}\n"

    return f"""
{config['SINGLE_TICKER']} BACKTEST RESULTS
============================================================

Configuration:
- Ticker:       {config['SINGLE_TICKER']}
- Timeframe:    {config['TIMEFRAME']}
- Date Range:   {start_date} to {end_date}
- EMA:          EMA {config['EMA_FAST']} / {config['EMA_SLOW']}

Performance:
- Total Trades: {len(df)}
- Wins:         {wins}
- Losses:       {losses}
- Win Rate:     {win_rate:.1f}%
- Net Profit:   ${net_profit:,.2f}
- Final Bal:    ${balance:,.2f}
- Avg Win:      ${avg_win:,.2f}
- Avg Loss:     ${avg_loss:,.2f}
- Max Win:      ${max_win:,.2f}
- Max Loss:     ${max_loss:,.2f}
{strategy_metrics}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""


def _create_results_folder():
    folder = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder, exist_ok=True)
    return folder