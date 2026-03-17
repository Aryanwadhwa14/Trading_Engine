def generate_signal(df):

    if len(df) < 5:
        return None

    latest = df.iloc[-1]
    prev1 = df.iloc[-2]
    prev2 = df.iloc[-3]
    prev3 = df.iloc[-4]

    ema_fast = latest["ema_fast"]
    ema_slow = latest["ema_slow"]

    close = latest["close"]
    open_ = latest["open"]

    # Candle type
    green = close > open_
    red = close < open_

    # Trend
    uptrend = ema_fast > ema_slow
    downtrend = ema_fast < ema_slow

    # =========================
    # 🔴 PRIORITY 1 — SCALP
    # =========================

    three_red = (
        (prev1["close"] < prev1["open"]) and
        (prev2["close"] < prev2["open"]) and
        (prev3["close"] < prev3["open"])
    )

    three_green = (
        (prev1["close"] > prev1["open"]) and
        (prev2["close"] > prev2["open"]) and
        (prev3["close"] > prev3["open"])
    )

    # SHORT SCALP
    if uptrend and three_red:

        entry = close
        sl = prev1["high"]
        risk = sl - entry

        if risk > 0:
            tp = entry - 1.2 * risk

            return {
                "signal": "SHORT",
                "type": "scalp",
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "reason": "3 Red Candles (Exhaustion)"
            }

    # LONG SCALP
    if downtrend and three_green:

        entry = close
        sl = prev1["low"]
        risk = entry - sl

        if risk > 0:
            tp = entry + 1.2 * risk

            return {
                "signal": "LONG",
                "type": "scalp",
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "reason": "3 Green Candles (Exhaustion)"
            }

    # =========================
    # 🔵 PRIORITY 2 — TREND
    # =========================

    # LONG TREND
    if uptrend and close > ema_fast:

        entry = close
        sl = prev1["low"]
        risk = entry - sl

        if risk > 0:
            tp = entry + 2.0 * risk

            return {
                "signal": "LONG",
                "type": "trend",
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "reason": "Break Above EMA Fast"
            }

    # SHORT TREND
    if downtrend and close < ema_slow:

        entry = close
        sl = prev1["high"]
        risk = sl - entry

        if risk > 0:
            tp = entry - 2.0 * risk

            return {
                "signal": "SHORT",
                "type": "trend",
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "reason": "Break Below EMA Slow"
            }

    return None