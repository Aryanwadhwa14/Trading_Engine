"""
EMA Pullback Strategy
=====================
All boolean conditions use explicit float() casts so that no pandas
Series ever appears inside a Python `and` / `or` / comparison expression.

Helper functions is_green() and is_red() centralise the candle-colour
check and guarantee a plain Python bool is returned every time.

Causal Timing:
- Every emitted signal carries an explicit `signal_time` (timestamp of the bar
  at close of which the signal was confirmed) and `available_at` (earliest time
  the signal is eligible for execution, i.e. start of next bar).
- Reference price is strictly the closing price of the completed bar.
"""

from __future__ import annotations

import pandas as pd
from strategies.base import Signal


# ── Candle helpers ─────────────────────────────────────────────────────────────

def is_green(candle) -> bool:
    """Return True if the candle closed above its open (bullish)."""
    return float(candle["close"]) > float(candle["open"])


def is_red(candle) -> bool:
    """Return True if the candle closed below its open (bearish)."""
    return float(candle["close"]) < float(candle["open"])


def is_body_between_emas(candle) -> bool:
    """Return True if the candle's open and close are between its fast and slow EMAs."""
    fast = float(candle["ema_fast"])
    slow = float(candle["ema_slow"])
    upper = max(fast, slow)
    lower = min(fast, slow)
    o = float(candle["open"])
    c = float(candle["close"])
    return (max(o, c) < upper) and (min(o, c) > lower)


# ── Signal generator ───────────────────────────────────────────────────────────

def generate_signal(df: pd.DataFrame, config: dict) -> Signal | None:
    """
    Analyse the latest completed candles and return a typed Signal or None.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: open, high, low, close, ema_fast, ema_slow
    config : dict
        Must contain strategy enablement flags and optional symbol/timeframe metadata

    Returns
    -------
    Signal or None
    """
    if len(df) < 5:
        return None

    # ── Extract rows as plain-dict-like objects ────────────────────────────────
    latest = df.iloc[-1]
    prev1  = df.iloc[-2]
    prev2  = df.iloc[-3]
    prev3  = df.iloc[-4]

    # Check for NaN in indicators (explicit warm-up check)
    if pd.isna(latest["ema_fast"]) or pd.isna(latest["ema_slow"]):
        return None

    # ── Timestamps for causal execution ───────────────────────────────────────
    try:
        signal_time = pd.Timestamp(latest.name)
    except Exception:
        signal_time = pd.Timestamp.now()

    if len(df) >= 2:
        try:
            bar_delta = pd.Timestamp(df.index[-1]) - pd.Timestamp(df.index[-2])
            available_at = signal_time + bar_delta
        except Exception:
            available_at = signal_time + pd.Timedelta(minutes=5)
    else:
        available_at = signal_time + pd.Timedelta(minutes=5)

    symbol = str(config.get("SINGLE_TICKER", "UNKNOWN"))
    timeframe = str(config.get("TIMEFRAME", "5m"))

    # ── Scalar extractions ────────────────────────────────────────────────────
    ema_fast = float(latest["ema_fast"])
    ema_slow = float(latest["ema_slow"])
    close    = float(latest["close"])

    # ── Trend flags (plain Python bools) ──────────────────────────────────────
    uptrend   = ema_fast > ema_slow
    downtrend = ema_fast < ema_slow

    # ── Multi-candle pattern flags ────────────────────────────────────────────
    three_red   = is_red(prev1)   and is_red(prev2)   and is_red(prev3)
    three_green = is_green(prev1) and is_green(prev2) and is_green(prev3)

    scalp_rr = float(config.get("SCALP_RR", 1.2))
    trend_rr = float(config.get("TREND_RR", 2.0))

    # =========================================================================
    # Strategy 3 → SHORT SCALP  (uptrend + 3 red exhaustion candles + 3rd closes below EMA 55)
    # =========================================================================
    if config.get("ENABLE_S3", False) and uptrend and three_red and float(prev1["close"]) > ema_slow and float(prev3["open"]) < ema_fast:
        entry = close
        sl    = float(prev3["open"])
        risk  = sl - entry

        if risk > 0:
            tp = entry - scalp_rr * risk
            return Signal(
                symbol=symbol,
                side="SHORT",
                signal_type="scalp",
                strategy_id=3,
                signal_time=signal_time,
                available_at=available_at,
                reference_price=entry,
                stop_loss=sl,
                take_profit=tp,
                timeframe=timeframe,
                reason="3 Red Candles (3rd closes below Slow EMA in Uptrend)",
            )

    # =========================================================================
    # Strategy 4 → LONG SCALP  (downtrend + 3 green exhaustion candles + 3rd closes above EMA 55)
    # =========================================================================
    if config.get("ENABLE_S4", False) and downtrend and three_green and float(prev1["close"]) > ema_fast and float(prev3["open"]) > ema_slow:
        entry = close
        sl    = float(prev3["open"])
        risk  = entry - sl

        if risk > 0:
            tp = entry + scalp_rr * risk
            return Signal(
                symbol=symbol,
                side="LONG",
                signal_type="scalp",
                strategy_id=4,
                signal_time=signal_time,
                available_at=available_at,
                reference_price=entry,
                stop_loss=sl,
                take_profit=tp,
                timeframe=timeframe,
                reason="3 Green Candles (3rd closes above Slow EMA in Downtrend)",
            )

    # =========================================================================
    # Strategy 1 → LONG TREND  (uptrend + previous candle between EMAs + close above fast EMA)
    # =========================================================================
    if config.get("ENABLE_S1", False) and uptrend and is_body_between_emas(prev1) and close > ema_fast:
        entry = close
        sl    = ema_slow
        risk  = entry - sl
        if risk > 0:
            tp = entry + trend_rr * risk
            return Signal(
                symbol=symbol,
                side="LONG",
                signal_type="trend",
                strategy_id=1,
                signal_time=signal_time,
                available_at=available_at,
                reference_price=entry,
                stop_loss=sl,
                take_profit=tp,
                timeframe=timeframe,
                reason="Prev Candle Between EMAs + Break Above EMA Fast (Trend Continuation)",
            )

    # =========================================================================
    # Strategy 2 → SHORT TREND  (downtrend + previous candle between EMAs + close below slow EMA)
    # =========================================================================
    if config.get("ENABLE_S2", False) and downtrend and is_body_between_emas(prev1) and close < ema_fast:
        entry = close
        sl    = ema_slow
        risk  = sl - entry
        if risk > 0:
            tp = entry - trend_rr * risk
            return Signal(
                symbol=symbol,
                side="SHORT",
                signal_type="trend",
                strategy_id=2,
                signal_time=signal_time,
                available_at=available_at,
                reference_price=entry,
                stop_loss=sl,
                take_profit=tp,
                timeframe=timeframe,
                reason="Prev Candle Between EMAs + Break Below EMA Slow (Trend Continuation)",
            )

    return None
