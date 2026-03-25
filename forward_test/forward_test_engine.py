"""
Forward Test Engine
===================
Runs the trading strategy in a live loop, fetching the latest market data
and printing signals to the console immediately.  Telegram alerts are sent
only for genuinely *new* signals (deduplication  by signal_key).

Debug-friendly defaults:
  - SLEEP_SECONDS = 10  (change to e.g. 60 for production)
  - Every loop iteration prints a heartbeat so you know it's alive.
  - Full tracebacks are printed on unexpected errors.
"""

import os
import csv
import time
import traceback
from datetime import datetime

from data.live_data_loader import load_live_data
from indicators.ema import calculate_ema
from strategies.ema_pullback import generate_signal
from alerts.telegram_bot import send_telegram_message


# ── Tunable constants ─────────────────────────────────────────────────────────

# Low value = fast feedback during debugging.
SLEEP_SECONDS = 5


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_latency_to_csv(ts: str, ticker: str, timeframe: str, fetch_ms: float, compute_ms: float, tg_ms: float):
    """Appends the captured latencies to a CSV file for long-term analysis."""
    os.makedirs("latency", exist_ok=True)
    file_path = "latency/latency_logs.csv"
    file_exists = os.path.isfile(file_path)
    
    with open(file_path, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Ticker", "Timeframe", "API_Fetch_ms", "Compute_ms", "Telegram_ms"])
        
        writer.writerow([
            ts, 
            ticker, 
            timeframe, 
            f"{fetch_ms:.1f}", 
            f"{compute_ms:.1f}", 
            f"{tg_ms:.1f}"
        ])

def _make_signal_key(signal: dict) -> tuple:
    """
    Build a compact, hashable key from the signal.
    Two signals are considered 'the same' if they share side, type,
    strategy, and entry price (rounded to 2 dp).
    This prevents duplicate Telegram alerts on consecutive loops.
    """
    return (
        signal["signal"],
        signal["type"],
        signal["strategy_id"],
        round(signal["entry"], 2),
    )


def _print_signal(signal: dict, config: dict) -> None:
    """Pretty-print a signal to the console with a timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    side_icon = "🟢" if signal["signal"] == "LONG" else "🔴"
    print(
        f"\n{'='*55}\n"
        f"  {side_icon}  NEW SIGNAL  [{ts}]\n"
        f"{'='*55}\n"
        f"  Ticker   : {config['TICKER']}\n"
        f"  Timeframe: {config['TIMEFRAME']}\n" 
        f"  Strategy : EMA {config['EMA_FAST']}/{config['EMA_SLOW']} -> Strategy {signal['strategy_id']}\n"
        f"  Side     : {signal['signal']}\n"
        f"  Entry    : {signal['entry']:.4f}\n"
        f"  Stop Loss: {signal['stop_loss']:.4f}\n"
        f"  Take Prof: {signal['take_profit']:.4f}\n"
        f"  Reason   : {signal['reason']}\n"
        f"{'='*55}\n"
    )


def _format_telegram(signal: dict, config: dict) -> str:
    """Format the Telegram alert message."""
    side_icon = "🟢 LONG" if signal["signal"] == "LONG" else "🔴 SHORT"
    return (
        f"🚨 TRADE SIGNAL\n\n"
        f"Ticker  : {config['TICKER']}\n"
        f"Strategy: EMA {config['EMA_FAST']}/{config['EMA_SLOW']} -> Strategy {signal['strategy_id']}\n"
        f"Timeframe: {config['TIMEFRAME']}\n"
        f"Side    : {side_icon}\n"
        f"Entry   : {signal['entry']:.4f}\n"
        f"SL      : {signal['stop_loss']:.4f}\n"
        f"TP      : {signal['take_profit']:.4f}\n\n"
        f"Reason:\n{signal['reason']}"
    )


# ── Main engine loop ──────────────────────────────────────────────────────────

def run_forward_test(config: dict) -> None:
    """
    Fetch live data, compute indicators, evaluate strategy,
    and fire alerts for new signals. Executes EXACTLY ONCE.

    Parameters
    ----------
    config : dict
        Must contain: TICKER, TIMEFRAME, EMA_FAST, EMA_SLOW
    """

    ticker    = config["TICKER"]
    timeframe = config["TIMEFRAME"]
    ema_fast  = config["EMA_FAST"]
    ema_slow  = config["EMA_SLOW"]
    
    # Context-Based Learning: Extract maximum indicator depths to inform the data layer 
    # dynamically how far into the past it must reach for the EMA math to burn in perfectly.
    max_ema   = max(int(ema_fast), int(ema_slow))

    print(f"\n[forward_test] 🚀 Executing Scanner Pipeline for {ticker} ({timeframe})")
    print(f"[forward_test]    EMA({ema_fast}) / EMA({ema_slow})\n")

    ts = datetime.now().strftime("%H:%M:%S")
    
    # Reset telemetry trackers for this run
    fetch_ms = 0.0
    compute_ms = 0.0
    tg_ms = 0.0

    print(f"[{ts}] Fetching live data for {ticker}…", end=" ", flush=True)

    try:
        # 1. Fetch and clean data (dynamic burn-in length)
        t_fetch_start = time.perf_counter()
        df = load_live_data(ticker=ticker, interval=timeframe, max_ema_length=max_ema)
        t_fetch_end = time.perf_counter()
        fetch_ms = (t_fetch_end - t_fetch_start) * 1000
        
        print(f"got {len(df)} rows, latest close={float(df['close'].iloc[-1]):.4f}  | ⏱ Fetch: {fetch_ms:.0f}ms")

        # 2. Compute indicators
        t_compute_start = time.perf_counter()
        df["ema_fast"] = calculate_ema(df, ema_fast)
        df["ema_slow"] = calculate_ema(df, ema_slow)

        # 3. Drop rows where indicators are NaN (warm-up period)
        df.dropna(subset=["ema_fast", "ema_slow"], inplace=True)

        if len(df) < 5:
            print(f"[{ts}] Not enough rows after indicator warm-up ({len(df)}), aborting.")
            _log_latency_to_csv(ts, ticker, timeframe, fetch_ms, 0.0, 0.0)
            return

        # 4. Evaluate strategy
        signal = generate_signal(df)
        t_compute_end = time.perf_counter()
        compute_ms = (t_compute_end - t_compute_start) * 1000

        # 5. Handle signal
        if signal:
            _print_signal(signal, config)

            try:
                t_tg_start = time.perf_counter()
                msg = _format_telegram(signal, config)
                send_telegram_message(msg)
                t_tg_end = time.perf_counter()
                tg_ms = (t_tg_end - t_tg_start) * 1000
                print(f"[{ts}] ✅ Telegram alert sent.  | ⏱ Compute: {compute_ms:.1f}ms | ⏱ Telegram: {tg_ms:.0f}ms")
            except Exception as tg_err:
                print(f"[{ts}] ⚠️  Telegram send failed: {tg_err}")

        else:
            print(f"[{ts}] No signal this bar.  | ⏱ Compute: {compute_ms:.1f}ms")

        # 6. Save permanent log to CSV
        _log_latency_to_csv(ts, ticker, timeframe, fetch_ms, compute_ms, tg_ms)

    except ValueError as ve:
        print(f"\n[{ts}] ⚠️  Data error: {ve}\n")

    except KeyError as ke:
        print(f"\n[{ts}] ❌ Column error: {ke}")
        traceback.print_exc()

    except Exception as exc:
        print(f"\n[{ts}] ❌ Unexpected error: {exc}")
        traceback.print_exc()