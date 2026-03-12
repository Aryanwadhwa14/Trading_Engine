

def generate_signal(df):

    if len(df) < 5:
        return None

    latest = df.iloc[-1]
    prev1 = df.iloc[-2]
    prev2 = df.iloc[-3]
    prev3 = df.iloc[-4]

    ema_fast = latest["ema_fast"]
    ema_slow = latest["ema_slow"]

    # candle color
    green = latest["close"] > latest["open"]
    red = latest["close"] < latest["open"]

    # trend
    uptrend = ema_fast > ema_slow
    downtrend = ema_fast < ema_slow

    # EMA band
    ema_high = max(ema_fast, ema_slow)
    ema_low = min(ema_fast, ema_slow)

    def between_emas(candle):
        return (candle["low"] <= ema_high) and (candle["high"] >= ema_low)

    # 3 candle triggers
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

    trigger_red = three_red and (
        between_emas(prev1) or
        between_emas(prev2) or
        between_emas(prev3)
    )

    trigger_green = three_green and (
        between_emas(prev1) or
        between_emas(prev2) or
        between_emas(prev3)
    )

    # Institutional Short
    if uptrend and red and trigger_red and latest["close"] < ema_fast and latest["close"] < ema_slow:
        return {
            "signal": "SHORT",
            "type": "scalp",
            "reason": "Institutional Short"
        }

    # Institutional Long
    if downtrend and green and trigger_green and latest["close"] > ema_slow:
        return {
            "signal": "LONG",
            "type": "scalp",
            "reason": "Institutional Long"
        }

    # Pullback Long
    if uptrend:
        if (prev1["low"] <= prev1["ema_fast"]) or (prev1["low"] <= prev1["ema_slow"]):
            if green:
                return {
                    "signal": "LONG",
                    "type": "trend",
                    "reason": "Pullback Long"
                }

    # Pullback Short
    if downtrend:
        if (prev1["high"] >= prev1["ema_fast"]) or (prev1["high"] >= prev1["ema_slow"]):
            if red:
                return {
                    "signal": "SHORT",
                    "type": "trend",
                    "reason": "Pullback Short"
                }

    return None