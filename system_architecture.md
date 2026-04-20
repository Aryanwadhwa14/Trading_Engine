# Trading Engine — System Architecture

> A modular, asset-agnostic algorithmic trading research system built on a microservice-inspired module structure.

---

## Table of Contents

1. [What "Asset-Agnostic" Means](#1-what-asset-agnostic-means)
2. [Why This Is Designed Like Microservices](#2-why-this-is-designed-like-microservices)
3. [Module Map — Every File Explained](#3-module-map--every-file-explained)
4. [How Data Flows Through the System](#4-how-data-flows-through-the-system)
5. [Full Runtime Flow — Backtest Mode](#5-full-runtime-flow--backtest-mode)
6. [Full Runtime Flow — Forward Test Mode](#6-full-runtime-flow--forward-test-mode)
7. [Full Runtime Flow — Factor Optimization Mode](#7-full-runtime-flow--factor-optimization-mode)
8. [The Contract System — How Modules Talk to Each Other](#8-the-contract-system--how-modules-talk-to-each-other)
9. [Configuration as the Control Panel](#9-configuration-as-the-control-panel)
10. [What Is Implemented vs Planned](#10-what-is-implemented-vs-planned)
11. [How to Extend This System](#11-how-to-extend-this-system)

---

## 1. What "Asset-Agnostic" Means

The entire engine was designed to work on **any tradeable asset** — not just NVDA, not just US stocks.

### Why it doesn't care what asset you give it

Every module in this system operates on a **standardised price table** (a DataFrame) with exactly these columns:

```
datetime (index) | open | high | low | close | volume
```

That's it. The system never asks:
- *"Is this a stock or crypto?"*
- *"Is this quoted in USD or BTC?"*
- *"Is this a futures contract?"*

It simply receives a table of candles and processes them.

### What this means in practice

Change **one line** in `config.py` and the entire engine runs on a completely different asset and market:

```python
# TODAY — US Equity (Daily)
"TICKER":    "NVDA",
"TIMEFRAME": "1d"

# TOMORROW — Crypto (1-hour)
"TICKER":    "BTC-USD",
"TIMEFRAME": "1h"

# NEXT WEEK — Forex (5-minute)
"TICKER":    "EURUSD=X",
"TIMEFRAME": "5m"

# BONDS (Daily)
"TICKER":    "TLT",
"TIMEFRAME": "1d"

# COMMODITY
"TICKER":    "GC=F",       # Gold Futures
"TIMEFRAME": "1d"
```

### Asset Compatibility Table

| Asset Class | Example Ticker | Timeframes Supported | Notes |
|---|---|---|---|
| US Equities | `NVDA`, `AAPL`, `SPY` | `1d`, `1h`, `5m`, `1m` | Any stock on NYSE/NASDAQ |
| Crypto | `BTC-USD`, `ETH-USD` | `1d`, `1h`, `5m` | Yahoo Finance format |
| Forex | `EURUSD=X`, `GBPUSD=X` | `1d`, `1h` | Yahoo Finance FX pairs |
| Bonds / ETFs | `TLT`, `AGG`, `BND` | `1d` | Bond ETFs work perfectly |
| Commodities | `GC=F` (Gold), `CL=F` (Oil) | `1d`, `1h` | Futures via Yahoo Finance |
| Indices | `^GSPC` (S&P500), `^NDX` | `1d` | Index tracking |

> **The key insight:** `yfinance` — the data source — supports all of these. Since the data layer normalises everything into the same column structure, the rest of the engine doesn't know or care what asset it's working with.

---

## 2. Why This Is Designed Like Microservices

A microservice architecture means each component is **independent, replaceable, and communicates through well-defined interfaces**.

This engine follows that same principle — but inside a single Python project.

### The Core Principle

```
Each module does ONE thing.
Each module can be swapped without touching the others.
Modules talk to each other through standard data contracts (DataFrames + dicts).
```

### Side-by-Side: Real Microservices vs This Engine

| Microservice Concept | In a Real App | In This Engine |
|---|---|---|
| **Service** | Independent deployed server | Independent Python module/folder |
| **Interface** | REST API (JSON in/out) | Function call (DataFrame in / dict out) |
| **Independence** | Can be restarted separately | Can be replaced without touching others |
| **Single responsibility** | Payment service handles only payments | `indicators/ema.py` handles only EMA |
| **Config** | Environment variables / service config | `config.py` |
| **Orchestrator** | API Gateway / message bus | `main.py` |

### Module Independence Proof

You could completely replace any of these without touching anything else:

| Module | What you could swap in | Nothing else changes |
|---|---|---|
| `data/historical_loader.py` | Replace yfinance with Alpaca, Binance API, CSV file | ✅ |
| `indicators/ema.py` | Replace EMA with VWAP, RSI, Bollinger Bands | ✅ |
| `strategies/ema_pullback.py` | Replace with MACD strategy, breakout strategy | ✅ |
| `backtest/backtest_engine.py` | Replace with vectorised backtester | ✅ |
| `alerts/telegram_bot.py` | Replace with Discord, email, SMS | ✅ |

---

## 3. Module Map — Every File Explained

```
Trading-engine/
│
├── config.py                        ← CONTROL PANEL
│       All strategy + system parameters live here.
│       Change ticker, timeframe, EMAs, balance, RR ratios.
│
├── main.py                          ← ORCHESTRATOR
│       Entry point. Calls each module in order.
│       Reads config → fetches data → calculates indicators
│       → runs backtest / forward test → saves results.
│
├── data/                            ╔══════════════════╗
│   ├── historical_loader.py         ║  DATA SERVICE    ║
│   │       Downloads and cleans     ║                  ║
│   │       historical OHLCV data    ║  Input:  config  ║
│   │       via yfinance.            ║  Output: df      ║
│   │                                ╚══════════════════╝
│   └── live_data_loader.py
│           Fetches latest candles
│           for forward testing.
│
├── indicators/                      ╔══════════════════╗
│   ├── ema.py                       ║ INDICATOR SERVICE║
│   │       Calculates Exponential   ║                  ║
│   │       Moving Average and adds  ║  Input:  df      ║
│   │       it as a column.          ║  Output: series  ║
│   │                                ╚══════════════════╝
│   └── atr.py
│           Calculates Average True
│           Range (volatility measure).
│
├── strategies/                      ╔══════════════════╗
│   └── ema_pullback.py              ║ STRATEGY SERVICE ║
│           The trading brain.       ║                  ║
│           Looks at recent candles  ║  Input:  df      ║
│           + EMA values → returns   ║  Output: signal  ║
│           a LONG/SHORT/None signal.║          dict    ║
│                                    ╚══════════════════╝
│
├── backtest/                        ╔══════════════════╗
│   └── backtest_engine.py           ║BACKTEST SERVICE  ║
│           Simulates trades on      ║                  ║
│           historical data.         ║  Input:  df +    ║
│           Replays every candle,    ║          config  ║
│           checks SL/TP, logs all   ║  Output: results ║
│           trades + summary stats.  ║          CSV+TXT ║
│                                    ╚══════════════════╝
│
├── forward_test/                    ╔══════════════════╗
│   └── forward_test_engine.py       ║  PAPER TRADING   ║
│           [PLANNED]                ║  SERVICE         ║
│           Runs strategy on live    ║                  ║
│           data in a loop. Paper    ║  Input:  live df ║
│           trades without real      ║  Output: signal  ║
│           money.                   ║          → alert ║
│                                    ╚══════════════════╝
│
├── execution/                       ╔══════════════════╗
│   └── position_sizing.py           ║ EXECUTION SERVICE║
│           [PLANNED]                ║                  ║
│           Calculates how many      ║  Input:  signal +║
│           shares/lots to buy       ║          balance ║
│           based on % risk.         ║  Output: qty     ║
│                                    ╚══════════════════╝
│
├── factors/                         ╔══════════════════╗
│   └── factors_engine.py            ║OPTIMISATION SVC  ║
│           [PLANNED]                ║                  ║
│           Grid search over         ║  Input:  param   ║
│           EMA periods, RR ratios   ║          ranges  ║
│           → finds best params.     ║  Output: ranked  ║
│                                    ║          results ║
│                                    ╚══════════════════╝
│
├── alerts/                          ╔══════════════════╗
│   └── telegram_bot.py              ║  ALERT SERVICE   ║
│           [PLANNED]                ║                  ║
│           Sends trade signal       ║  Input:  signal  ║
│           messages to Telegram     ║  Output: message ║
│           chat via bot API.        ║          to chat ║
│                                    ╚══════════════════╝
│
├── latency/                         ← TELEMETRY STORE
│       latency_logs.csv             ← API, compute, and Telegram send times
│
└── results/                         ← OUTPUT STORE
        run_YYYYMMDD_HHMMSS/
            trade_log.csv            ← Every trade in detail
            summary.txt              ← Performance metrics
```

---

## 4. How Data Flows Through the System

The system passes data between modules in a **single direction** — like an assembly line.

### The Standard Data Contract

Every module speaks the same "language" — a pandas DataFrame with this structure:

```
Index:   datetime         (e.g. 2025-09-01, 2025-09-02 ...)
Columns:
  open       float        (e.g. 912.50)
  high       float        (e.g. 918.40)
  low        float        (e.g. 907.20)
  close      float        (e.g. 915.00)
  volume     int          (e.g. 38500000)
  ema_fast   float        (added by indicators/ema.py)
  ema_slow   float        (added by indicators/ema.py)
  atr        float        (added by indicators/atr.py)
```

### Data Assembly Line

```
STEP 1 — RAW DATA
┌─────────────────────────────────────────────────┐
│  historical_loader.py / live_data_loader.py     │
│                                                 │
│  downloads from yfinance                        │
│  normalises columns to lowercase                │
│  sets datetime index                            │
│                                                 │
│  OUTPUT:  df [open, high, low, close, volume]   │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
STEP 2 — ADD INDICATORS
┌─────────────────────────────────────────────────┐
│  indicators/ema.py × 2    indicators/atr.py     │
│                                                 │
│  df["ema_fast"] = calculate_ema(df, 26)         │
│  df["ema_slow"] = calculate_ema(df, 55)         │
│  df["atr"]      = calculate_atr(df, 14)         │
│                                                 │
│  OUTPUT:  df [+ ema_fast, ema_slow, atr cols]   │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
STEP 3 — GENERATE SIGNALS (per candle)
┌─────────────────────────────────────────────────┐
│  strategies/ema_pullback.py                     │
│                                                 │
│  generate_signal(df_up_to_current_candle)       │
│                                                 │
│  → checks last 4 candles                        │
│  → checks EMA trend direction                   │
│  → checks candle colour patterns                │
│  → picks highest priority strategy              │
│                                                 │
│  OUTPUT:  {"signal": "LONG",                    │
│            "type":   "trend",                   │
│            "strategy_id": 1,                    │
│            "entry": 915.00,                     │
│            "stop_loss": 907.20,                 │
│            "take_profit": 929.80,               │
│            "reason": "Break Above EMA Fast"}    │
│           or None (no trade)                    │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
STEP 4 — SIMULATE / ALERT
┌─────────────────────────────────────────────────┐
│  backtest_engine.py    OR    forward_engine.py  │
│                                                 │
│  BACKTEST:  simulate SL/TP hit on next candles  │
│  FORWARD:   send signal dict to alert service   │
│                                                 │
│  OUTPUT:  trade_log.csv + summary.txt           │
│           OR: Telegram message                  │
└─────────────────────────────────────────────────┘
```

---

## 5. Full Runtime Flow — Backtest Mode

This is the **currently active mode**.

```
python main.py
      │
      ▼
[1] CONFIG LOADED
      config.py → CONFIG dict:
      TICKER="NVDA", TIMEFRAME="1d",
      START_DATE="2025-09-01", END_DATE="2026-02-17",
      EMA_FAST=26, EMA_SLOW=55, ATR=14,
      INITIAL_BALANCE=10000
      │
      ▼
[2] DATA FETCH
      historical_loader.load_historical_data(
          ticker="NVDA",
          interval="1d",
          period="5y"
      )
      → yfinance downloads 5 years of NVDA daily OHLCV
      → columns flattened + renamed to lowercase
      → df returned with datetime index
      │
      ▼
[3] DATE FILTER
      df = df[ (df.index >= "2025-09-01") &
               (df.index <= "2026-02-17") ]
      → only the configured date window kept
      │
      ▼
[4] INDICATOR CALCULATION
      df["ema_fast"] = calculate_ema(df, 26)
      df["ema_slow"] = calculate_ema(df, 55)
      df["atr"]      = calculate_atr(df, 14)
      → 3 new columns added to the same df
      │
      ▼
[5] BACKTEST ENGINE STARTS
      run_backtest(df, config, start_date, end_date)
      │
      ├── position = 0  (no trade open)
      ├── balance  = $10,000
      ├── trade_log = []
      │
      └── for i in range(5, len(df)):        ← candle loop
              │
              ├── current_df = df[:i+1]      ← history up to now
              ├── row        = df[i]         ← current candle
              │
              ├── IF position == 0:
              │       signal = generate_signal(current_df)
              │       │
              │       ├── checks Strategy 3 (Short Scalp) first
              │       ├── checks Strategy 4 (Long Scalp) second
              │       ├── checks Strategy 1 (Trend Long) third
              │       └── checks Strategy 2 (Trend Short) last
              │
              │       if signal found:
              │           position  = +1 (LONG) or -1 (SHORT)
              │           entry_price, stop_loss, take_profit stored
              │
              ├── IF position == +1 (LONG):
              │       if low  <= stop_loss  → SL Hit → exit
              │       if high >= take_profit → TP Hit → exit
              │       pnl = exit_price - entry_price
              │       balance += pnl
              │       trade_log.append(trade_record)
              │       position = 0
              │
              └── IF position == -1 (SHORT):
                      if high >= stop_loss   → SL Hit → exit
                      if low  <= take_profit → TP Hit → exit
                      pnl = entry_price - exit_price
                      balance += pnl
                      trade_log.append(trade_record)
                      position = 0
      │
      ▼
[6] RESULTS GENERATION
      _create_results_folder()
      → creates: results/run_20260317_221000/

      trades_df.to_csv("trade_log.csv")
      → every trade: date, side, type, strategy_id,
                     entry, SL, TP, exit, PnL, result

      _generate_summary(trades_df)
      → total trades, wins, losses, win rate,
         net profit, avg win, avg loss, max win, max loss
      → printed to terminal + saved as summary.txt
```

---

## 6. Full Runtime Flow — Forward Test Mode

> **Status: Live** — `forward_test_engine.py` is fully implemented and running.

The real-time flow is:

```
python main.py  (with MODE="forward" in config)
      │
      ▼
[1] CONFIG LOADED (same config.py)
      │
      ▼
[2] LIVE DATA FETCH (runs on a loop)
      live_data_loader.fetch_live_data(
          ticker="NVDA",
          interval="1d",
          lookback="60d"        ← enough for EMA warm-up
      )
      → downloads latest 60 days of candles
      → same normalisation as historical loader
      │
      ▼
[3] INDICATOR CALCULATION (same functions, same df)
      df["ema_fast"] = calculate_ema(df, 26)
      df["ema_slow"] = calculate_ema(df, 55)
      df["atr"]      = calculate_atr(df, 14)
      │
      ▼
[4] SIGNAL GENERATION
      signal = generate_signal(df)
      → same generate_signal() function
      → runs on the LATEST candle only
      │
      ▼
[5] POSITION SIZING (planned: execution/position_sizing.py)
      qty = calculate_position_size(
          balance=10000,
          risk_pct=0.01,
          entry=signal["entry"],
          sl=signal["stop_loss"]
      )
      → how many shares to buy
      │
      ▼
[6] ALERT SENT (planned: alerts/telegram_bot.py)
      send_telegram_alert(signal, qty)
      →  TRADE SIGNAL
         Ticker: NVDA
         Direction: LONG
         Entry: 915.00
         SL: 907.20
         TP: 929.80
         Qty: 12 shares
      │
      ▼
[7] SLEEP → WAIT FOR NEXT CANDLE
      sleep(until next candle close)
      → daily: sleep 24h
      → 1h:    sleep 1h
      → 5m:    sleep 5m
      │
      └──────────────────────────► LOOP BACK TO STEP 2
```

---

## 7. Full Runtime Flow — Factor Optimization Mode

> **Status: Planned** — `factors_engine.py` is created but empty.

When implemented:

```
python main.py  (with MODE="factor")
      │
      ▼
[1] DEFINE PARAMETER GRID (in config or factors engine)

      EMA_FAST_RANGE  = [9, 15, 20, 26]
      EMA_SLOW_RANGE  = [30, 50, 55, 100]
      TREND_RR_RANGE  = [1.5, 2.0, 2.5, 3.0]
      SCALP_RR_RANGE  = [1.0, 1.2, 1.5]
      │
      ▼
[2] GRID SEARCH LOOP

      results = []

      for fast in EMA_FAST_RANGE:
        for slow in EMA_SLOW_RANGE:
          for rr_trend in TREND_RR_RANGE:
            for rr_scalp in SCALP_RR_RANGE:

              → override config with these params
              → run full backtest pipeline
              → capture: win_rate, net_profit, total_trades
              → append to results[]
      │
      ▼
[3] RANK RESULTS

      Sort by: net_profit DESC
               win_rate   DESC
               total_trades > minimum threshold

      → Best config printed to terminal
      → Full results grid saved as factor_results.csv
      │
      ▼
[4] USE BEST PARAMS

      → Update config.py with winning combination
      → Run normal backtest to confirm
```

---

## 8. The Contract System — How Modules Talk to Each Other

Instead of complex message buses or APIs, modules in this engine communicate through **standardised Python objects**. These are the contracts every module must honour.

### Contract 1 — The DataFrame (df)

Every module that touches price data must accept and return this format:

```
Required columns:  open, high, low, close, volume
Required index:    datetime (pd.DatetimeIndex)
Column types:      float64 for OHLCV, float64 for indicators
```

Any module that adds computed values extends the same df:

```
df["ema_fast"]   → float64 series, length = len(df)
df["ema_slow"]   → float64 series, length = len(df)
df["atr"]        → float64 series, length = len(df)
```

### Contract 2 — The Signal Dict

`generate_signal()` must always return either `None` or a dict with exactly these keys:

```python
{
    "signal":      str,    # "LONG" or "SHORT"
    "type":        str,    # "trend" or "scalp"
    "strategy_id": int,    # 1, 2, 3, or 4
    "entry":       float,  # entry price
    "stop_loss":   float,  # stop loss price
    "take_profit": float,  # take profit price
    "reason":      str     # human-readable reason
}
```

The backtest engine and forward engine both read exactly these keys. If `generate_signal()` returns something different, the engines break — this is the interface contract.

### Contract 3 — The Trade Record

Every exit event logged by `_log_trade()` must produce a dict with these keys — used to build `trade_log.csv`:

```python
{
    "Trade Date":    date,
    "Ticker":        str,
    "Timeframe":     str,    # e.g., "1d", "5m"
    "Side":          str,    # "LONG" or "SHORT"
    "Trade Type":    str,    # "TREND" or "SCALP"
    "Strategy No":   int,
    "Entry Time":    datetime, # stored with PST timezone formatting
    "Entry Price":   float,
    "Stop Loss":     float,
    "Take Profit":   float,
    "Exit Time":     datetime, # stored with PST timezone formatting
    "Exit Price":    float,
    "Duration (min)":int,
    "Entry Reason":  str,
    "Exit Reason":   str,    # "SL Hit" or "TP Hit"
    "PnL ($)":       float,
    "Result":        str     # "WIN" or "LOSS"
}
```

---

## 9. Configuration as the Control Panel

`config.py` is the **single source of truth** for all parameters. Nothing is hardcoded in any module.

```python
CONFIG = {

    # ─── ASSET ──────────────────────────────────
    "TICKER_ENABILITY": "single",    # toggle "single" or "multi"
    "SINGLE_TICKER":   "NVDA",
    "MULTI_TICKER":    ["NVDA", "AAPL", "TSLA"],
    "TIMEFRAME":       "1d",         # "1m", "5m", "15m", "1h", "4h", "1d", "1wk"

    # ─── BACKTEST DATE WINDOW ────────────────────
    "START_DATE":      "2025-09-01",
    "END_DATE":        "2026-02-17",

    # ─── INDICATORS ─────────────────────────────
    "EMA_FAST":        26,
    "EMA_SLOW":        55,
    "ATR_PERIOD":      14,

    # ─── CAPITAL & RISK ─────────────────────────
    "INITIAL_BALANCE": 10000,        # starting account in USD
    "RISK_PERCENT":    0.01,         # 1% risk per trade

    # ─── STRATEGY RR ────────────────────────────
    "TREND_RR":        2.0,          # trend trades:  risk 1 → target 2
    "SCALP_RR":        1.2,          # scalp trades:  risk 1 → target 1.2

    # ─── BACKTEST CONTROL ───────────────────────
    "MAX_TRADES":      10000,        # safety cap

    # ─── OUTPUT ─────────────────────────────────
    "SAVE_RESULTS":    True,
    "RESULTS_FOLDER":  "results"
}
```

### How changing TICKER + TIMEFRAME changes everything

```
TICKER = "BTC-USD", TIMEFRAME = "1h"

→ historical_loader downloads Bitcoin 1-hour candles
→ same EMA26/55 calculated on BTC 1h closes
→ same generate_signal() checks 4 candles of BTC 1h data
→ same backtest simulates BTC LONG/SHORT trades
→ same results folder created with BTC performance stats

Zero code change. Only config.py changed.
```

---

## 10. What Is Implemented vs Planned

### Live (Fully Working)

| Module | File | Status |
|---|---|---|
| Historical data loader | `data/historical_loader.py` | ✅ Complete |
| Live data loader | `data/live_data_loader.py` | ✅ Complete |
| EMA indicator | `indicators/ema.py` | ✅ Complete |
| ATR indicator | `indicators/atr.py` | ✅ Complete |
| EMA 4-strategy signal engine | `strategies/ema_pullback.py` | ✅ Complete |
| Backtest engine | `backtest/backtest_engine.py` | ✅ Complete |
| Config system | `config.py` | ✅ Complete |
| Main orchestrator | `main.py` | ✅ Complete |
| Forward test engine | `forward_test/forward_test_engine.py` | ✅ Complete |
| Telegram alerts | `alerts/telegram_bot.py` | ✅ Complete |

### Planned (Files Created, Logic Empty)

| Module | File | What It Will Do |
|---|---|---|
| Position sizing | `execution/position_sizing.py` | Calculate share qty from risk % |
| Factor engine | `factors/factors_engine.py` | Grid search parameter optimisation |

---

## 11. How to Extend This System

### Add a New Strategy

1. Create `strategies/my_new_strategy.py`
2. Implement `generate_signal(df) → dict or None`
3. Return a dict matching the Signal Contract (Section 8)
4. In `main.py`, import your strategy instead of `ema_pullback`

The backtest engine, forward engine, and alert system all work immediately — they only see the signal dict, not the strategy code.

### Add a New Indicator

1. Create `indicators/my_indicator.py`
2. Implement `calculate_X(df, period) → pd.Series`
3. In `main.py`, add: `df["my_indicator"] = calculate_X(df, period)`
4. Use `df["my_indicator"]` inside your strategy

### Add a New Asset

Change `config.py` only:

```python
"TICKER_ENABILITY": "single",
"SINGLE_TICKER":    "ETH-USD",
"TIMEFRAME":        "4h"
```

### Add a New Alert Channel (Email, Discord, etc)

1. Create `alerts/discord_bot.py` (or `email_sender.py`)
2. Implement `send_alert(signal_dict) → None`
3. Call it from `forward_test_engine.py` instead of or alongside `telegram_bot.py`

### Add a New Data Source (Alpaca, Binance, CSV)

1. Create `data/alpaca_loader.py`
2. Implement `load_data(ticker, interval) → df` matching the DataFrame contract
3. Swap it in `main.py`

The rest of the pipeline —> data loading, indicators, strategy, backtest, forward_test — work without any changes.

### Built-In Multi-Asset Scanner (Automated Trading)

Because `forward_test_engine.py` executes exactly *once* and cleanly exits, this engine now wraps the system into an automated multi-asset real-time scanner natively through the config payload!
1. Change `TICKER_ENABILITY` to `"multi"`.
2. Define a list of tickers: `"MULTI_TICKER": ["NVDA", "AAPL", "MSFT"]`.
3. The `main.py` orchestrator will automatically iterate across these tickers during the live `while True:` loop inside your Python environment.
4. It calls `run_forward_test(CONFIG)` for each ticker dynamically, swapping the active ticker variable sequentially.

---

## Architecture Summary Diagram

```
                    ┌─────────────────────────────────┐
                    │           config.py              │
                    │  TICKER / TIMEFRAME / EMA        │
                    │  DATES / BALANCE / RR            │
                    └────────────────┬────────────────┘
                                     │ (all modules read config)
                                     │
          ┌───────────────────────── ▼ ───────────────────────────┐
          │                       main.py                         │
          │                    (ORCHESTRATOR)                      │
          └──┬─────────────────────────────────────────────────┬──┘
             │                                                 │
    BACKTEST MODE                                    FORWARD MODE
             │                                                 │
             ▼                                                 ▼
   ┌──────────────────┐                          ┌──────────────────┐
   │ historical_loader│                          │ live_data_loader │
   │  (yfinance API)  │                          │  (yfinance API)  │
   └────────┬─────────┘                          └────────┬─────────┘
            │  df [OHLCV]                                 │  df [OHLCV]
            ▼                                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                     indicators/                              │
   │   ema.py  →  df["ema_fast"],  df["ema_slow"]                │
   │   atr.py  →  df["atr"]                                      │
   └──────────────────────────┬───────────────────────────────────┘
                              │  df [OHLCV + indicators]
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │               strategies/ema_pullback.py                     │
   │                   generate_signal(df)                        │
   │                                                              │
   │   Strategy 3 (Short Scalp, priority 1)                      │
   │   Strategy 4 (Long Scalp,  priority 2)                      │
   │   Strategy 1 (Trend Long,  priority 3)                      │
   │   Strategy 2 (Trend Short, priority 4)                      │
   │                                                              │
   │   → returns signal dict  OR  None                           │
   └──────────┬───────────────────────────────────────┬──────────┘
              │                                       │
    BACKTEST PATH                             FORWARD PATH
              │                                       │
              ▼                                       ▼
   ┌──────────────────┐                   ┌────────────────────┐
   │ backtest_engine  │                   │ position_sizing.py │
   │                  │                   │ [PLANNED]          │
   │ loops all candles│                   │ qty from risk %    │
   │ checks SL/TP     │                   └──────────┬─────────┘
   │ logs every trade │                              │
   └────────┬─────────┘                              ▼
            │                             ┌────────────────────┐
            ▼                             │  telegram_bot.py   │
   ┌──────────────────┐                   │  [PLANNED]         │
   │  results/        │                   │  sends to Telegram │
   │  trade_log.csv   │                   └────────────────────┘
   │  summary.txt     │
   └──────────────────┘

                    ┌─────────────────────────────────┐
                    │        factors_engine.py         │
                    │           [PLANNED]              │
                    │                                  │
                    │  loops EMA/RR combinations       │
                    │  runs backtest for each          │
                    │  ranks by performance            │
                    └─────────────────────────────────┘
```

---

*Last updated: 2026-03-17 | Engine version: EMA 4-Strategy (Live) | Asset: NVDA 1d*
