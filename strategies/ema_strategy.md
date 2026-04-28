# EMA Pullback Strategy — Full Documentation

**File:** `strategies/ema_pullback.py`  
**Purpose:** The strategy's brain — looks at the last few candles and decides whether to go LONG, SHORT, or do nothing.

---

## What Does This File Do?

This is a **4-in-1 strategy engine**. It contains one function — `generate_signal()` — that looks at the latest price candles and the two EMA lines, then picks the best trade to take (if any).

It does **not** execute any trade. It simply returns a **signal dictionary** telling the backtest engine what the trade should look like.

---

## The Two Indicators Used

| Indicator | What it means |
|---|---|
| **EMA Fast** (e.g., EMA 26) | A faster-reacting average price line — responds quickly to price changes |
| **EMA Slow** (e.g., EMA 55) | A slower-reacting average price line — shows the bigger trend |

**Quick Trend Rule:**
- `EMA Fast > EMA Slow` → **Uptrend** (market is generally going up)
- `EMA Fast < EMA Slow` → **Downtrend** (market is generally going down)

---

## Function — `generate_signal(df)` *(Lines 1–115)*

### Plain English Explanation

This function receives the **full price history up to the current candle** and returns either:
- A **signal dictionary** (if a trade setup is found), or
- `None` (if no clear setup exists — do nothing)

---

### Setting Up Candle Variables (Lines 3–21)

```python
if len(df) < 5:
    return None

latest = df.iloc[-1]   # current (most recent) candle
prev1  = df.iloc[-2]   # 1 candle ago
prev2  = df.iloc[-3]   # 2 candles ago
prev3  = df.iloc[-4]   # 3 candles ago

ema_fast = latest["ema_fast"]
ema_slow = latest["ema_slow"]

close  = latest["close"]
open_  = latest["open"]

green = close > open_   # current candle is bullish (price went up)
red   = close < open_   # current candle is bearish (price fell)

uptrend   = ema_fast > ema_slow
downtrend = ema_fast < ema_slow
```

> **What is happening here?**  
> We're collecting the last 4 candles and labelling key facts about them:
> - Are we in an uptrend or downtrend?
> - Is the current candle green (bullish) or red (bearish)?
> - What are the EMA values right now?

> **Safety Check:** If there are fewer than 5 candles, we can't reliably judge pattern → return `None`.

---

## Priority System

The strategy checks patterns in **priority order** — highest priority first:

```
Priority 1 → Strategy 3 (Short Scalp)  ← checked first
Priority 2 → Strategy 4 (Long Scalp)
Priority 3 → Strategy 1 (Trend Long)
Priority 4 → Strategy 2 (Trend Short)  ← checked last
```

> **Why priority?** Because scalp signals (institutional reversals) are considered higher confidence when they appear. If both a scalp signal and a trend signal exist at the same time, the scalp wins.

---

## Strategy 3 — Short Scalp (Lines 39–55)

### When Does It Trigger?

```
Market is in an UPTREND
+ 1st red candle closes ABOVE the fast EMA
+ 2nd red candle forms BETWEEN the fast and slow EMAs
+ 3rd red candle closes BELOW the slow EMA
```

### Plain English

> Imagine the market has been going up (uptrend). A distinct sequence of 3 red candles steps down through the moving averages — starting above the fast EMA, pausing perfectly between them, and finally breaking decisively below the slow EMA. Big players are reversing the local trend. We ride that short-term drop.

### Code Explained

```python
s3_pattern = (
    is_red(prev3) and float(prev3["close"]) > ema_fast and
    is_red(prev2) and is_body_between_emas(prev2) and
    is_red(prev1) and float(prev1["close"]) < ema_slow
)

if uptrend and s3_pattern:
    entry = close           # enter at current price
    sl    = ema_fast        # v3.2: stop loss = fast ema
    risk  = sl - entry

    if risk > 0:
        tp = entry - 1.2 * risk     # take profit = 1.2× the risk below entry
```

| Value | What it means |
|---|---|
| `entry` | Current closing price — where we enter the SHORT |
| `sl` (stop loss) | High of the previous candle — if price goes above here, the short thesis is wrong |
| `sl` | **v3.1**: High of first red candle (`prev3`) — if price goes above here, the short thesis is wrong 
| `risk` | Distance from entry to stop loss |
| `tp` (take profit) | Entry minus 1.2× risk — targeting a small but quick move down |
| `1.2 RR` | Risk:Reward ratio of 1.2 — for every $1 risked, we target $1.20 profit |

### Signal Returned

```python
{
    "signal": "SHORT",
    "type": "scalp",
    "strategy_id": 3,
    "entry": ...,
    "stop_loss": ...,
    "take_profit": ...,
    "reason": "Red-Red-Red Pattern crossing EMAs downwards in Uptrend"
}
```

---

## Strategy 4 — Long Scalp (Lines 57–73)

### When Does It Trigger?

```
Market is in a DOWNTREND
+ 1st green candle closes BELOW the slow EMA
+ 2nd green candle forms BETWEEN the fast and slow EMAs
+ 3rd green candle closes ABOVE the slow EMA
```

### Plain English

> The market has been falling. Suddenly, a distinct 3 green pattern breaks up through the moving averages — starting below the slow EMA, and decisively breaking above the slow EMA with a green candle. Institutions are buying the reversal. We ride that short-term bounce up.

### Code Explained

```python
s4_pattern = (
    is_green(prev3) and float(prev3["close"]) < ema_slow and
    is_green(prev2) and is_body_between_emas(prev2) and
    is_green(prev1) and float(prev1["close"]) > ema_slow
)

if downtrend and s4_pattern:
    entry = close
    sl    = ema_fast        # v4.2: stop loss = fast ema
    risk  = entry - sl

    if risk > 0:
        tp = entry + 1.2 * risk
```

| Value | What it means |
|---|---|
| `entry` | Current close — enter the LONG |
| `sl` | **v4.1**: Low of first green candle (`prev3`) — if price drops below here, the bounce failed |
| `tp` | Entry plus 1.2× risk — small profit target on the bounce |

### Signal Returned

```python
{
    "signal": "LONG",
    "type": "scalp",
    "strategy_id": 4,
    ...
    "reason": "Green-Red-Green Pattern crossing EMAs upwards in Downtrend"
}
```

---

## Strategy 1 — Trend Long (Lines 79–95)

### When Does It Trigger?

```
Market is in an UPTREND (ema_fast > ema_slow)
+ The previous candle formed entirely BETWEEN the fast and slow EMAs
+ Current candle closes ABOVE the fast EMA
```

### Plain English

> The market is going up. It pulled back to the point where the previous candle was resting exactly between the two EMAs. Now, the current candle just broke back above the fast EMA — a sign that the uptrend is resuming perfectly out of the pullback zone. We go LONG.

### Code Explained

```python
if uptrend and is_body_between_emas(prev1) and close > ema_fast:
    entry = close
    # sl = prev2["low"]     # v1.1: stop loss = low of 2 candles ago
    sl    = ema_slow        # v1.2: stop loss = slow EMA value
    risk  = entry - sl

    if risk > 0:
        tp = entry + 2 * risk   # take profit = 2× risk (RR of 2)
```

| Value | What it means |
|---|---|
| `sl` | **v1.1**: Low of 2 candles ago (`prev2`).<br>**v1.2**: Value of `ema_slow` (Current Active Logic). |
| `tp` | Entry + 2× risk — trend trades target bigger moves, hence RR = 2.0 |
| `2.0 RR` | For every $1 risked, we target $2.00 profit |

### Signal Returned

```python
{
    "signal": "LONG",
    "type": "trend",
    "strategy_id": 1,
    ...
    "reason": "Prev Candle Between EMAs + Break Above EMA Fast (Trend Continuation)"
}
```

---

## Strategy 2 — Trend Short (Lines 97–113)

### When Does It Trigger?

```
Market is in a DOWNTREND (ema_fast < ema_slow)
+ The previous candle formed entirely BETWEEN the fast and slow EMAs
+ Current candle closes BELOW the slow EMA
```

### Plain English

> The market is falling. It pulled back upward so the previous candle rested completely between the two EMAs. Then, the current candle broke heavily downward, closing below the slow EMA. This confirms the downtrend is picking up pace. We go SHORT.

### Code Explained

```python
if downtrend and is_body_between_emas(prev1) and close < ema_slow:
    entry = close
    # sl = prev2["high"]    # v2.1: stop loss = high of 2 candles ago
    sl    = ema_slow        # v2.2: stop loss = slow EMA value
    risk  = sl - entry

    if risk > 0:
        tp = entry - 2 * risk
```

| Value | What it means |
|---|---|
| `sl` | **v2.1 **: High of 2 candles ago (`prev2`).<br>**v2.2**: Value of `ema_slow` (Current Active Logic). |
| `tp` | Entry minus 2× risk — targeting a 2:1 R:R move down |

### Signal Returned

```python
{
    "signal": "SHORT",
    "type": "trend",
    "strategy_id": 2,
    ...
    "reason": "Prev Candle Between EMAs + Break Below EMA Slow (Trend Continuation)"
}
```

---

## Final Return (Line 115)

```python
return None
```

> If none of the 4 strategies found a valid setup, the function returns `None` — meaning: **"No trade this candle. Wait."**

---

## All 4 Strategies at a Glance

| # | Name | Market | Trigger | Direction | RR | Type |
|---|---|---|---|---|---|---|
| 1 | Trend Long | Uptrend | Prev Candle In EMAs + Close > EMA Fast | LONG | 2.0 | Trend |
| 2 | Trend Short | Downtrend | Prev Candle In EMAs + Close < EMA Slow | SHORT | 2.0 | Trend |
| 3 | Scalp Short | Uptrend | Red-Red-Red cross down | SHORT | 1.2 | Scalp |
| 4 | Scalp Long | Downtrend | Green-Red-Green cross up | LONG | 1.2 | Scalp |

---

## Key Concepts for Non-Coders

| Term | Plain English |
|---|---|
| **df.iloc[-1]** | The most recent row (candle) in the table |
| **df.iloc[-2]** | One candle before the latest |
| **`close > open`** | Green candle — price went up during that candle |
| **`close < open`** | Red candle — price fell during that candle |
| **Risk** | Distance between entry price and stop loss |
| **RR (Risk:Reward)** | If RR is 2.0 and you risk $100, target is $200 profit |
| **Scalp** | Short-duration trade targeting quick small moves |
| **Trend trade** | Longer trade following the dominant market direction |
| **`return None`** | No signal found — engine stays out of the market |
| **signal dictionary** | A Python dict with all trade details neatly labelled |