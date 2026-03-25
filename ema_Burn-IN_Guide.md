# The Quant's Guide to Indicator Burn-In

When transitioning an algorithmic trading strategy from a static historical backtest to a live, ticking forward-test (or live trading environment), one of the most hidden mathematically disastrous issues an algorithm can face is **Indicator "Burn-In" Deficiency**.

## 1. What is Burn-In?

In quantitative finance, technical indicators generally fall into two categories:

### Finite Impulse Response (FIR) Filters
*Examples: Simple Moving Average (SMA), Pivot Points, Donchian Channels.*
These indicators only "see" a strict, fixed window of history. A 20-period SMA *only* mathematically cares about the last 20 candles. If you feed the algorithm exactly 21 candles of data, the SMA will be 100% accurate and mathematically identical to your backtester.

### Infinite Impulse Response (IIR) Filters
*Examples: Exponential Moving Average (EMA), MACD, RSI, ATR.*
These indicators are mathematically recursive. The calculation for today's value explicitly requires yesterday's value.
For example, the formula for an EMA is:
> `EMA_today = (Value_today * Multiplier) + (EMA_yesterday * (1 - Multiplier))`

Because today's calculation needs yesterday's calculation, which needed the day before that... an EMA is infinitely recursive. Today's EMA still contains a tiny microscopic mathematical fraction of **the very first candle ever traded on that ticker**.

Because you cannot realistically download 100 years of tick data on every loop of a live forward testing engine, your live engine must download a smaller "window" (like 1 month) and start its EMA calculation from the top of that window. The start of the calculation creates an unavoidable math error (usually assuming the first EMA is just an SMA), which slowly fades out as it processes more and more rows downwards through the dataframe. 

By the time the calculation reaches the *live* candle at the bottom of the dataframe, the EMA has "burned in" and the error has faded to zero.

## 2. The Quant Rule of Thumb

To ensure the starting mathematical error fully dissipates before generating a live signal, **you must fetch at least 3x to 5x the longest indicator period** in historical setup candles.

* **Example:** Trading an `EMA(200)`
* **Rule:** You need `200 * 4 = 800` historical candles in the dataframe *before* looking at the live candle.

## 3. The Implementation in our Live Engine

Previously, our data loader was hardcoded to fetch `period="5d"` (5 days) of data, regardless of the timeframe.

While 5 days of a 5-minute crypto market (24/7) generates 1,440 candles (plenty of burn-in for a 200 EMA), 5 days of a 15-minute US Stock market generates only 130 candles (Not enough to burn in a 200 EMA, leading to false live signals).

**The Solution:**
The [live_data_loader.py](file:///d:/Aryan/Trading-engine/data/live_data_loader.py) is now context-aware:
1. It looks at the maximum EMA used by your strategy (`max_ema = 200`).
2. It mathematically demands at least `800` candles.
3. It maps your timeframe (e.g., `15m`) to determine exactly how many days of history are required to yield 800 candles.
4. It calls the broker/API (`yfinance`) with the optimal [period](file:///d:/Aryan/Trading-engine/data/live_data_loader.py#5-57) parameter (e.g., `"1mo"`, `"60d"`) avoiding API limits while guaranteeing mathematically pure, perfectly synced indicators!
