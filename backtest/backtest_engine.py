import os
import pandas as pd
from datetime import datetime
from strategies.ema_pullback import generate_signal


def run_backtest(df, config, start_date, end_date):

    balance = config.get("INITIAL_BALANCE", 10000)
    ticker = config["TICKER"]

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
                    ticker, "LONG", trade_type, strategy_id,
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
                    ticker, "SHORT", trade_type, strategy_id,
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

def _log_trade(ticker, side, trade_type, strategy_id,
               entry_time, entry_price,
               sl, tp,
               exit_time, exit_price,
               entry_reason, exit_reason,
               pnl):

    return {
        "Trade Date": entry_time.date(),
        "Ticker": ticker,
        "Side": side,
        "Trade Type": trade_type.upper(),
        "Strategy No": strategy_id,
        "Entry Time": entry_time,
        "Entry Price": round(entry_price, 2),
        "Stop Loss": round(sl, 2),
        "Take Profit": round(tp, 2),
        "Exit Time": exit_time,
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

    return f"""
{config['TICKER']} BACKTEST RESULTS
============================================================

Configuration:
- Ticker:       {config['TICKER']}
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

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""


def _create_results_folder():
    folder = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder, exist_ok=True)
    return folder