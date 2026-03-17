# NVDA Swing Engine — Signal Logic Implementation Plan

> **Scope:** [services/NVIDIA_backtest/main.py](file:///d:/Aryan/ema9_backtest/services/NVIDIA_backtest/main.py) only.
> Forex and QQQ engines are NOT touched.

---

## Problem

Current `pullback_long`/`pullback_short` conditions are too loose.
`low.shift(1) <= ema_fast.shift(1)` fires on almost every candle in an uptrend
(since EMA26 is the upper line in uptrend, nearly every prior candle's low is below it).
This causes entries mid-trend instead of at actual pullback zones.

---

## Four Strategies to Implement

### Strategy 1 — Trend Long (Pullback → BUY)

| Step | Condition |
|---|---|
| **Trigger (N−1)** | Candle overlaps the EMA zone: `low ≤ ema_fast` AND `high ≥ ema_slow` |
| **Entry (N)** | Uptrend + green candle + `close > ema_slow` (bounced back above lower EMA) |

```python
prev_in_zone_long = (
    df["low"].shift(1)  <= df["ema_fast"].shift(1)
) & (
    df["high"].shift(1) >= df["ema_slow"].shift(1)
)

df["trend_long"] = (
    df["uptrend"] &
    prev_in_zone_long &
    (df["close"] > df["open"]) &
    (df["close"] > df["ema_slow"])
)
```

---

### Strategy 2 — Trend Short (Pullback → SHORT)

| Step | Condition |
|---|---|
| **Trigger (N−1)** | Candle overlaps the EMA zone: `high ≥ ema_slow` AND `low ≤ ema_fast` |
| **Entry (N)** | Downtrend + red candle + `close < ema_slow` (rejected back below upper EMA) |

```python
prev_in_zone_short = (
    df["high"].shift(1) >= df["ema_slow"].shift(1)
) & (
    df["low"].shift(1)  <= df["ema_fast"].shift(1)
)

df["trend_short"] = (
    df["downtrend"] &
    prev_in_zone_short &
    (df["close"] < df["open"]) &
    (df["close"] < df["ema_slow"])
)
```

---

### Strategy 3 — Institutional Short (3 Red trigger → SHORT)

| Step | Condition |
|---|---|
| **Trigger (N−3, N−2, N−1)** | 3 consecutive red candles, ALL strictly between both EMAs |
| **Entry (N)** | Red candle, `close < ema_fast` AND `close < ema_slow` (breaks below zone) |

> **User correction:** Entry candle closes **below both EMAs** — not above ema_fast.

```python
three_red_trigger = (
    df["red"].shift(1) & df["between_emas"].shift(1) &
    df["red"].shift(2) & df["between_emas"].shift(2) &
    df["red"].shift(3) & df["between_emas"].shift(3)
)

df["inst_short"] = (
    df["uptrend"] &
    df["red"] &
    (df["close"] < df["ema_fast"]) &
    (df["close"] < df["ema_slow"]) &
    three_red_trigger
)
```

---

### Strategy 4 — Institutional Long (3 Green trigger → LONG)

| Step | Condition |
|---|---|
| **Trigger (N−3, N−2, N−1)** | 3 consecutive green candles, ALL strictly between both EMAs |
| **Entry (N)** | Green candle, `close > ema_slow` (breaks above the upper EMA in downtrend) |

> **User correction:** Entry candle closes **above ema_slow** (which is the upper line in downtrend since EMA55 > EMA26 when downtrend).

```python
three_green_trigger = (
    df["green"].shift(1) & df["between_emas"].shift(1) &
    df["green"].shift(2) & df["between_emas"].shift(2) &
    df["green"].shift(3) & df["between_emas"].shift(3)
)

df["inst_long"] = (
    df["downtrend"] &
    df["green"] &
    (df["close"] > df["ema_slow"]) &
    three_green_trigger
)
```

---

## Helper Column: `between_emas`

A candle is **strictly between** the EMAs when its wicks overlap the band:

```python
ema_hi = df[["ema_fast", "ema_slow"]].max(axis=1)
ema_lo = df[["ema_fast", "ema_slow"]].min(axis=1)
df["between_emas"] = (df["low"] <= ema_hi) & (df["high"] >= ema_lo)
```

---

## Priority Order in Backtest Loop

```
PRIORITY 1 (Institutional):   inst_short  →  inst_long
PRIORITY 2 (Trend Pullback):  trend_short →  trend_long
```

> Only one trade open at a time. Institutional signals fire first if both are present on same bar.

---

## Risk Management (unchanged)

| Parameter | Value |
|---|---|
| Risk per trade | 1% of balance |
| Stop Loss | `1.5 × ATR(14)` from entry |
| Take Profit | `2.0 × risk` from entry |
| Position size | [(balance × 0.01) / risk_per_share] |

---