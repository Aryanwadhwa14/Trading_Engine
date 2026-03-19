"""
Forward Test Engine
===================
Runs the trading strategy in a live loop, fetching the latest market data
and printing signals to the console immediately.  Telegram alerts are sent
only for genuinely *new* signals (deduplication by signal_key).

Debug-friendly defaults:
  - SLEEP_SECONDS = 10  (change to e.g. 60 for production)
  - Every loop iteration prints a heartbeat so you know it's alive.
  - Full tracebacks are printed on unexpected errors.
"""

import time
import traceback
from datetime import datetime

from data.live_data_loader import load_live_data
from indicators.ema import calculate_ema
from strategies.ema_pullback import generate_signal
from alerts.telegram_bot import send_telegram_message


# ── Tunable constants ─────────────────────────────────────────────────────────

# Low value = fast feedback during debugging.  Set to 60 for 1-min bars in prod.
SLEEP_SECONDS = 10


# ── Internal helpers ──────────────────────────────────────────────────────────

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
        f"  Strategy : #{signal['strategy_id']} — {signal['type'].upper()}\n"
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
        f"Strategy: #{signal['strategy_id']} ({signal['type'].upper()})\n"
        f"Side    : {side_icon}\n"
        f"Entry   : {signal['entry']:.4f}\n"
        f"SL      : {signal['stop_loss']:.4f}\n"
        f"TP      : {signal['take_profit']:.4f}\n\n"
        f"Reason:\n{signal['reason']}"
    )


# ── Main engine loop ──────────────────────────────────────────────────────────

def run_forward_test(config: dict) -> None:
    """
    Continuously fetch live data, compute indicators, evaluate strategy,
    and fire alerts for new signals.

    Parameters
    ----------
    config : dict
        Must contain: TICKER, TIMEFRAME, EMA_FAST, EMA_SLOW
    """

    ticker    = config["TICKER"]
    timeframe = config["TIMEFRAME"]
    ema_fast  = config["EMA_FAST"]
    ema_slow  = config["EMA_SLOW"]

    last_signal_key = None   # tracks the most recent signal to avoid duplicates
    loop_count      = 0

    print(f"\n[forward_test] 🚀 Starting live forward test for {ticker} ({timeframe})")
    print(f"[forward_test]    EMA({ema_fast}) / EMA({ema_slow})  |  sleep={SLEEP_SECONDS}s\n")

    while True:
        loop_count += 1
        ts = datetime.now().strftime("%H:%M:%S")

        # ── Heartbeat ─────────────────────────────────────────────────────────
        print(f"[{ts}] Loop #{loop_count} — fetching data for {ticker}…", end=" ", flush=True)

        try:
            # 1. Fetch and clean data
            df = load_live_data(ticker=ticker, interval=timeframe)
            print(f"got {len(df)} rows, latest close={float(df['close'].iloc[-1]):.4f}")

            # 2. Compute indicators
            df["ema_fast"] = calculate_ema(df, ema_fast)
            df["ema_slow"] = calculate_ema(df, ema_slow)

            # 3. Drop rows where indicators are NaN (warm-up period)
            df.dropna(subset=["ema_fast", "ema_slow"], inplace=True)

            if len(df) < 5:
                print(f"[{ts}] Not enough rows after indicator warm-up ({len(df)}), skipping.")
                time.sleep(SLEEP_SECONDS)
                continue

            # 4. Evaluate strategy
            signal = generate_signal(df)

            # 5. Handle signal
            if signal:
                signal_key = _make_signal_key(signal)

                if signal_key != last_signal_key:
                    # New signal — print + alert
                    _print_signal(signal, config)

                    try:
                        msg = _format_telegram(signal, config)
                        send_telegram_message(msg)
                        print(f"[{ts}] ✅ Telegram alert sent.")
                    except Exception as tg_err:
                        # Telegram failure must not crash the engine
                        print(f"[{ts}] ⚠️  Telegram send failed: {tg_err}")

                    last_signal_key = signal_key

                else:
                    print(f"[{ts}] Signal unchanged ({signal['signal']} #{signal['strategy_id']}), skipping duplicate alert.")

            else:
                print(f"[{ts}] No signal this bar.")

        except ValueError as ve:
            # Data quality / empty-data errors — log and continue
            print(f"\n[{ts}] ⚠️  Data error: {ve}\n")

        except KeyError as ke:
            # Column mismatch errors — log full traceback for diagnosis
            print(f"\n[{ts}] ❌ Column error: {ke}")
            traceback.print_exc()

        except Exception as exc:
            # Unexpected errors — log but never crash the loop
            print(f"\n[{ts}] ❌ Unexpected error: {exc}")
            traceback.print_exc()

        # ── Wait before next iteration ─────────────────────────────────────
        time.sleep(SLEEP_SECONDS)