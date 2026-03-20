# Trading Engine – Algorithmic Trading Research & Signal System

## Overview

**Trading Engine** is a modular algorithmic trading research system built to research, test, and eventually deploy rule-based trading strategies — starting with EMA-based setups.

The system is designed around a clean **separation of concerns** — data flows in one direction, each layer does exactly one job:

| Layer | What It Does |
|---|---|
| `data/` | Fetches and cleans historical or live market price data |
| `indicators/` | Calculates technical indicators (EMA, ATR) from price data |
| `strategies/` | Generates trade signals (LONG / SHORT / None) |
| `backtest/` | Simulates trades on historical data and produces performance stats |
| `forward_test/` | Runs strategy on live data without real money (paper trading) |
| `factors/` | Tests combinations of parameters to find the best settings |
| `execution/` | Calculates position size based on account risk |
| `alerts/` | Sends trade signals directly to Telegram |
| `config.py` | Central settings file — change everything from one place |
| `main.py` | Entry point — orchestrates the full pipeline |

Currently active: **EMA Pullback Strategy** with 4 sub-strategies (2 trend + 2 scalp).

---

# What aryan have implemented till now : 
```
data/
    historical_loader.py

indicators/
    ema.py
    atr.py

strategies/
    ema_pullback.py

backtest/
   backtest_engine.py

forward_test/
   forward_test_engine.py

alerts/
   telegram_bot.py

config.py -> added different modes "backtest" and "forward"

main.py
```  

# To Do next : 
```
factors/
    factor_engine.py

execution/
    position_sizing.py

alerts/
    telegram_bot.py  -> update the alerts 

config.py

main.py
```

# System Architecture

```
trading_engine/
│
├── data/
│   ├── historical_loader.py        ← downloads & cleans price data
│   ├── live_data_loader.py         ← fetches latest candles for paper trading
│
├── indicators/
│   ├── ema.py                      ← Exponential Moving Average
│   ├── atr.py                      ← Average True Range (volatility)
│
├── strategies/
│   ├── ema_pullback.py             ← 4-strategy signal engine
│   ├── ema_strategy.md             ← Full strategy documentation
│
├── backtest/
│   ├── backtest_engine.py          ← Simulates trades on historical data
│   ├── backtest_engine.md          ← Full engine documentation
│
├── forward_test/
│   ├── forward_engine.py           ← Live paper trading loop
│
├── factors/
│   ├── factor_engine.py            ← Parameter optimization / grid search
│
├── execution/
│   ├── position_sizing.py          ← Position size calculation from risk %
│
├── alerts/
│   ├── telegram_bot.py             ← Sends trade signals to Telegram
│
├── config.py                       ← All settings in one place
├── main.py                         ← Entry point — runs the full pipeline
└── README.md
```

---

# Core System Flow

```
Market Data  (historical_loader / live_data_loader)
     │
     ▼
Indicators   (ema.py → adds ema_fast, ema_slow columns)
     │        (atr.py → adds atr column)
     ▼
Strategy     (ema_pullback.py → returns signal dict or None)
     │
     ▼
Backtest     (backtest_engine.py → loops candles, simulates SL/TP exits)
     │
     ▼
Results      (trade_log.csv + summary.txt → saved in results/run_TIMESTAMP/)
```

---

# Module Explanation

---

# Data Layer

## Purpose

The **data layer** provides market data to the trading system. It is the first step of the pipeline — everything else depends on clean, properly formatted price data.

Two types of data are used:

* **Historical data** → for backtesting (replay of the past)
* **Live data** → for forward testing (paper trading)

---

## historical_loader.py

Loads historical market data used for backtesting. Under the hood it uses `yfinance` to download OHLCV price data from Yahoo Finance.

Responsibilities:

* Download historical price data for any ticker
* Clean and normalize the dataset (lowercase columns, datetime index)
* Return a standardized DataFrame ready for indicator calculation

Expected output format:

```
datetime (index) | open | high | low | close | volume
```

Important rules:

* Index must be **datetime**
* Column names must be **lowercase**
* Data must be **chronologically sorted** (oldest → newest)

---

## live_data_loader.py

Fetches the most recent candles for forward testing / paper trading.

Responsibilities:

* Retrieve latest market data for the configured ticker
* Provide sufficient historical candles for indicator warm-up
* Return the same format as `historical_loader`

Indicators require **warm-up data** before becoming reliable.

Example:

```
EMA 55 needs at least ~200 candles to stabilise
```

---

# Indicator Engine

Indicators are separated into their own modules so they can be reused across any strategy.

```
indicators/
    ema.py
    atr.py
```

Ouput columns added to the DataFrame:

```
df["ema_fast"]   ← EMA of period EMA_FAST (e.g. 26)
df["ema_slow"]   ← EMA of period EMA_SLOW (e.g. 55)
df["atr"]        ← ATR of period ATR_PERIOD (e.g. 14)
```

---

## ema.py

Calculates the **Exponential Moving Average (EMA)** — a smoothed average that gives more weight to recent prices.

EMA formula:

```
EMA = Price × k + EMA_previous × (1 − k)
k   = 2 / (period + 1)
```

Implementation uses pandas:

```python
df["close"].ewm(span=period, adjust=False).mean()
```

`adjust=False` is critical — it ensures the EMA matches the **standard trading platform EMA** (e.g. TradingView).

Currently configured:

```
EMA_FAST = 26
EMA_SLOW = 55
```

---

## atr.py

Calculates **Average True Range (ATR)** — a measure of how much a market moves on average per candle.

Used for:

* Stop-loss placement (kept for future use)
* Risk management
* Position sizing

True Range formula:

```
TR = max(
    high − low,
    abs(high − previous_close),
    abs(low  − previous_close)
)
```

ATR = rolling mean of TR over `ATR_PERIOD` candles (currently 14).

---

# Strategy Layer

```
strategies/
    ema_pullback.py
    ema_strategy.md   ← Full strategy documentation (see this file)
```

This layer generates **trade signals only** — it never executes anything.

The strategy (`ema_pullback.py`) implements **4 sub-strategies** divided into two types:

| Type | Strategies | RR | Priority |
|---|---|---|---|
| Scalp (Institutional) | Strategy 3 (Short), Strategy 4 (Long) | 1.2 | High |
| Trend | Strategy 1 (Long), Strategy 2 (Short) | 2.0 | Low |

Signal output structure:

```python
{
    "signal":      "LONG" / "SHORT",
    "type":        "trend" / "scalp",
    "strategy_id": 1 / 2 / 3 / 4,
    "entry":       price,
    "stop_loss":   price,
    "take_profit": price,
    "reason":      "Break Above EMA Fast"   # human-readable trigger
}
```

If no setup is found → returns `None` (no trade).

📄 **See full strategy docs:** [`strategies/ema_strategy.md`](strategies/ema_strategy.md)

---

# Backtesting Engine

```
backtest/
    backtest_engine.py
    backtest_engine.md   ← Full engine documentation (see this file)
```

The backtesting engine **replays historical data candle by candle** and simulates exactly what would happen if the strategy were live.

How it works:

```
1. Loop through every candle (starting from candle 5)
2. If no position → ask strategy for a signal
3. If signal → enter trade (store entry, SL, TP)
4. If in LONG → check if low hit SL or high hit TP → exit
5. If in SHORT → check if high hit SL or low hit TP → exit
6. Log every trade with full details
7. After all candles → compute summary stats
```

Metrics generated:

```
Total Trades    Win Rate       Net Profit
Wins / Losses   Avg Win        Avg Loss
Max Win         Max Loss       Final Balance
```

Output files saved per run:

```
results/
  run_YYYYMMDD_HHMMSS/
      trade_log.csv   ← every trade with all details
      summary.txt     ← overall performance stats
```

📄 **See full engine docs:** [`backtest/backtest_engine.md`](backtest/backtest_engine.md)

---

# Configuration System — `config.py`

All system parameters live in one place. Change anything here — no need to touch strategy or engine code.

Current config:

```python
CONFIG = {

    # ASSET
    "TICKER":          "NVDA",
    "TIMEFRAME":       "1d",        # daily candles

    # DATE RANGE
    "START_DATE":      "2025-09-01",
    "END_DATE":        "2026-02-17",

    # INDICATORS
    "EMA_FAST":        26,
    "EMA_SLOW":        55,
    "ATR_PERIOD":      14,

    # CAPITAL & RISK
    "INITIAL_BALANCE": 10000,       # starting $10,000
    "RISK_PERCENT":    0.01,        # 1% risk per trade (future use)

    # STRATEGY
    "TREND_RR":        2.0,         # Trend trades: 1:2 RR
    "SCALP_RR":        1.2,         # Scalp trades: 1:1.2 RR

    # BACKTEST CONTROL
    "MAX_TRADES":      10000,

    # OUTPUT
    "SAVE_RESULTS":    True,
    "RESULTS_FOLDER":  "results"
}
```

---

# Main Entry Point — `main.py`

`main.py` is the **single command** that runs the entire pipeline.

```python
python main.py
```

What it does step by step:

```
1. Load config from config.py
2. Download historical data (yfinance)
3. Filter to START_DATE → END_DATE
4. Calculate EMA Fast, EMA Slow, ATR
5. Run backtest_engine
6. Save trade_log.csv + summary.txt
7. Print summary to terminal
```

---

# Complete Workflows

## Backtesting Mode (Currently Active)

```
main.py
   │
   ▼
historical_loader  → downloads NVDA 1d from yfinance
   │
   ▼
ema.py + atr.py    → adds EMA26, EMA55, ATR14 columns
   │
   ▼
ema_pullback.py    → checks each candle for signals
   │
   ▼
backtest_engine    → simulates entries/exits, tracks PnL
   │
   ▼
results/           → trade_log.csv + summary.txt
```

---

## Forward Testing Mode (Live)

```
main.py
   │
   ▼
live_data_loader   → fetches latest candles
   │
   ▼
ema.py + atr.py
   │
   ▼
ema_pullback.py    → generates signal on latest candle
   │
   ▼
position_sizing.py → calculates shares based on account risk
   │
   ▼
telegram_bot.py    → sends alert to Telegram
   │
   ▼
sleep(next_candle) → waits and repeats
```

---

# Risk & Execution Engine — `execution/position_sizing.py`

Calculates **how many shares to buy** based on account risk settings.

Formula:

```
Risk per trade = Account Balance × Risk %
Shares         = Risk / (Entry Price − Stop Loss)
```

Example with current config (`RISK_PERCENT = 0.01`, `INITIAL_BALANCE = $10,000`):

```
Risk         = $10,000 × 1% = $100
SL Distance  = $2
Shares       = $100 / $2 = 50 shares
```

---

# Factor Engine — `factors/factor_engine.py`

Used for **parameter optimization** — runs the backtest across many combinations of parameters to find the best-performing settings.

Example grid search:

```python
for fast in [9, 15, 26]:
    for slow in [30, 55, 100]:
        for rr in [1.5, 2.0, 2.5]:
            run_backtest(fast, slow, rr)
```

Finds the combination that maximises win rate, net profit, or any other target metric.

---

# Telegram Alert System — `alerts/telegram_bot.py`

Sends trade signals directly to a Telegram chat when the forward testing engine generates a signal.

Setup:

```
1. Create bot via @BotFather on Telegram
2. Get BOT_TOKEN and CHAT_ID
3. Store in .env file
```

Example alert format:

```
TRADE SIGNAL

Ticker:     NVDA
Timeframe:  1D
Strategy:   EMA 26/55 → Strategy 1

Direction:  LONG
Type:       Trend

Entry:      912.50
Stop Loss:  905.10
Take Profit: 927.30
```

---

# Development Roadmap

| Phase | Module | Status |
|---|---|---|
| 1 | `data/historical_loader.py` | ✅ Done |
| 2 | `indicators/ema.py`, `atr.py` | ✅ Done |
| 3 | `strategies/ema_pullback.py` | ✅ Done |
| 4 | `backtest/backtest_engine.py` | ✅ Done |
| 5 | `execution/position_sizing.py` | 🔲 Planned |
| 6 | `forward_test/forward_test_engine.py` | ✅ Done |
| 7 | `alerts/telegram_bot.py` | ✅ Done |
| 8 | `factors/factor_engine.py` | 🔲 Planned |

---

# Future Improvements

* Walk-forward testing (avoid overfitting)
* Portfolio backtesting (multiple assets)
* Multi-timeframe analysis (e.g. daily + 1h confluence)
* Monte Carlo simulation (robustness testing)
* Machine learning signal filters
* Live trade execution via broker API

---

# License

MIT License
