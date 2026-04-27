"""
EMA Pullback Strategy
=====================
All boolean conditions use explicit float() casts so that no pandas
Series ever appears inside a Python `and` / `or` / comparison expression.

Helper functions is_green() and is_red() centralise the candle-colour
check and guarantee a plain Python bool is returned every time.
"""


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

def generate_signal(df):
    """
    Analyse the latest candles and return a signal dict or None.

    All values extracted from the DataFrame are explicitly cast to float
    to avoid the 'truth value of a Series is ambiguous' error that occurs
    when yfinance multi-index columns are not fully normalised.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: open, high, low, close, ema_fast, ema_slow

    Returns
    -------
    dict or None
    """

    if len(df) < 5:
        return None

    # ── Extract rows as plain-dict-like objects ────────────────────────────────
    # .iloc[-N] returns a pandas Series (one row).  Calling float() on each
    # individual element extracts the scalar and eliminates any residual
    # Series wrapping that yfinance multi-index columns can leave behind.

    latest = df.iloc[-1]
    prev1  = df.iloc[-2]
    prev2  = df.iloc[-3]
    prev3  = df.iloc[-4]

    # ── Scalar extractions ────────────────────────────────────────────────────
    ema_fast = float(latest["ema_fast"])
    ema_slow = float(latest["ema_slow"])
    close   = float(latest["close"])
    open   = float(latest["open"])

    # ── Trend flags (plain Python bools) ─────────────────────────────────────
    uptrend   = ema_fast > ema_slow
    downtrend = ema_fast < ema_slow

    # ── Multi-candle pattern flags ────────────────────────────────────────────
    three_red   = is_red(prev1)   and is_red(prev2)   and is_red(prev3)
    three_green = is_green(prev1) and is_green(prev2) and is_green(prev3)

    # =========================================================================
    # Strategy 3 → SHORT SCALP  (uptrend + 3 red exhaustion candles + 3rd closes below EMA 55)
    # =========================================================================
    if uptrend and three_red and float(prev1["close"]) < ema_slow:
        entry = open
        sl    = ema_fast # S3.2 (sl = fast ema -> ema 26)
        risk  = sl - entry

        if risk > 0:
            tp = entry - 1.2 * risk
            return {
                "signal":      "SHORT",
                "type":        "scalp",
                "strategy_id": 3,
                "entry":       entry,
                "stop_loss":   sl,
                "take_profit": tp,
                "reason":      "3 Red Candles (3rd closes below Slow EMA in Uptrend)",
            }

    # =========================================================================
    # Strategy 4 → LONG SCALP  (downtrend + 3 green exhaustion candles + 3rd closes above EMA 55)
    # =========================================================================
    if downtrend and three_green and float(prev1["close"]) > ema_slow:
        entry = open
        sl    = ema_fast # S4.2 (sl = fast ema -> ema 26)
        risk  = entry - sl

        if risk > 0:
            tp = entry + 1.2 * risk
            return {
                "signal":      "LONG",
                "type":        "scalp",
                "strategy_id": 4,
                "entry":       entry,
                "stop_loss":   sl,
                "take_profit": tp,
                "reason":      "3 Green Candles (3rd closes above Slow EMA in Downtrend)",
            }

    # =========================================================================
    # Strategy 1 → LONG TREND  (uptrend + previous candle between EMAs + close above fast EMA)
    # =========================================================================
    if uptrend and is_body_between_emas(prev1) and close > ema_fast:
        entry = close
        sl    = ema_slow  # sl = ema_slow -> strategy 1.2
        risk  = entry - sl
        if risk > 0:
            tp = entry + 2 * risk
            return {
                "signal":      "LONG",
                "type":        "trend",
                "strategy_id": 1,
                "entry":       entry,
                "stop_loss":   sl,
                "take_profit": tp,
                "reason":      "Prev Candle Between EMAs + Break Above EMA Fast (Trend Continuation)",
            }

    # =========================================================================
    # Strategy 2 → SHORT TREND  (downtrend + previous candle between EMAs + close below slow EMA)
    # =========================================================================
    if downtrend and is_body_between_emas(prev1) and close < ema_slow:
        entry = close
        sl    = ema_slow # sl = ema_slow -> strategy 2.2
        risk  = sl - entry
        if risk > 0: 
            tp = entry - 2 * risk
            return {
                "signal":      "SHORT",
                "type":        "trend",
                "strategy_id": 2,
                "entry":       entry,
                "stop_loss":   sl,
                "take_profit": tp,
                "reason":      "Prev Candle Between EMAs + Break Below EMA Slow (Trend Continuation)",
            }

    return None