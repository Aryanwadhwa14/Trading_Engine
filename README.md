# Trading Engine – Algorithmic Trading Research & Signal System

## Overview

**Trading Engine** is a modular algorithmic trading framework designed for:

* Strategy research
* Historical backtesting
* Forward testing (paper trading)
* Factor optimization
* Telegram-based trade signal alerts

The system is built to separate **data, indicators, strategies, execution logic, and alerts**, allowing strategies to be tested and deployed in a structured research environment.

This project currently focuses on **EMA-based strategies**, but the architecture supports building and testing any strategy.

---

# System Architecture

```
trading_engine/
│
├── data/
│   ├── historical_loader.py
│   ├── live_data_loader.py
│
├── indicators/
│   ├── ema.py
│   ├── atr.py
│
├── strategies/
│   ├── ema_pullback.py
│
├── backtest/
│   ├── backtest_engine.py
│
├── forward_test/
│   ├── forward_engine.py
│
├── factors/
│   ├── factor_engine.py
│
├── execution/
│   ├── position_sizing.py
│
├── alerts/
│   ├── telegram_bot.py
│
├── config.py
│
└── main.py
```

---

# Core System Flow

```
Market Data
     │
     ▼
Indicators
     │
     ▼
Strategy
     │
     ▼
Risk Model
     │
     ▼
Signal Generation
     │
     ▼
Telegram Alert
```

---

# Module Explanation

---

# Data Layer

## Purpose

The **data layer** provides market data to the trading system.

Two types of data are used:

* **Historical data** → for backtesting
* **Live data** → for forward testing

---

## historical_loader.py

Loads historical market data used for backtesting.

Responsibilities:

* Download historical price data
* Clean and normalize the dataset
* Return a standardized dataframe

Expected dataframe format:

```
datetime | open | high | low | close | volume
```

Important rules:

* Index must be **datetime**
* Column names must be **lowercase**
* Data must be **chronologically sorted**

---

## live_data_loader.py

Fetches the most recent candles for forward testing.

Responsibilities:

* Retrieve latest market data
* Provide sufficient history for indicator warm-up
* Return the same format as historical_loader

Indicators require **warm-up data** before becoming stable.

Example:

```
EMA 30 requires approximately 150 candles
```

---

# Indicator Engine

Indicators are separated into their own modules to allow reuse across strategies.

```
indicators/
    ema.py
    atr.py
```

---

## ema.py

Calculates the **Exponential Moving Average (EMA)**.

EMA formula:

```
EMA = Price × k + EMA_previous × (1 − k)
```

Where:

```
k = 2 / (period + 1)
```

Implementation uses pandas:

```
ewm(span=period, adjust=False)
```

Important parameter:

```
adjust=False
```

This ensures the calculation matches the **standard trading EMA**.

---

## atr.py

Calculates **Average True Range (ATR)**.

ATR measures market volatility and is commonly used for:

* Stop-loss placement
* Risk management
* Position sizing

True Range formula:

```
TR = max(
    high − low,
    abs(high − previous_close),
    abs(low − previous_close)
)
```

ATR is calculated as a rolling mean of TR.

---

# Strategy Layer

```
strategies/
    ema_pullback.py
```

This module generates **trade signals only**.

It must **not execute trades**.

Output signals include:

```
LONG
SHORT
NONE
```

Example strategy logic:

```
Uptrend: EMA_FAST > EMA_SLOW
Pullback: price touches EMA
Entry: bullish confirmation candle
```

Strategy output structure:

```
{
    "signal": "LONG",
    "entry": price,
    "stop_loss": price,
    "take_profit": price
}
```

---

# Backtesting Engine

```
backtest/backtest_engine.py
```

The backtesting engine simulates trades on historical data.

Backtesting process:

```
Load historical data
Calculate indicators
Generate strategy signals
Simulate trades
Track PnL
Compute performance metrics
```

Typical metrics generated:

```
Win Rate
Net Profit
Average Win
Average Loss
Max Drawdown
Sharpe Ratio
Profit Factor
```

Backtest execution loop:

```
for candle in dataset:

    evaluate entry signals

    if position open:
        manage stop loss
        manage take profit

    log results
```

---

# Forward Testing Engine

```
forward_test/forward_engine.py
```

Forward testing runs the strategy on **live market data** without executing real trades.

This is also known as:

```
Paper Trading
```

Forward testing loop:

```
while True:

    fetch latest market data

    compute indicators

    generate strategy signal

    send alert

    wait for next candle
```

Typical loop delay:

```
sleep(60)    → 1 minute timeframe
sleep(3600)  → 1 hour timeframe
```

---

# Risk & Execution Engine

```
execution/
    position_sizing.py
```

Responsible for calculating **position size** based on risk.

Position sizing formula:

```
Risk per trade = Account Balance × Risk %
```

Shares calculation:

```
shares = risk / (entry_price − stop_loss)
```

Example:

Account size:

```
$10,000
```

Risk per trade:

```
1% = $100
```

If stop-loss distance is:

```
$2
```

Shares:

```
100 / 2 = 50 shares
```

---

# Factor Engine

```
factors/
    factor_engine.py
```

Used for **parameter optimization and strategy research**.

Example parameter search:

```
EMA_FAST = [8, 10, 12]
EMA_SLOW = [20, 30, 50]
ATR_SL   = [1.2, 1.5, 2]
RR       = [1.5, 2, 3]
```

Grid search example:

```
for fast in EMA_FAST:
 for slow in EMA_SLOW:
  for sl in ATR_SL:

      run_backtest()
```

Results identify the **best-performing strategy parameters**.

---

# Telegram Alert System

```
alerts/
    telegram_bot.py
```

Used to send **trade alerts directly to Telegram**.

Create a Telegram bot using:

```
@BotFather
```

You will receive:

```
BOT_TOKEN
CHAT_ID
```

Example alert message:

```
TRADE SIGNAL

Ticker: NVDA
Strategy: EMA Pullback

Direction: LONG

Entry: 912.50
Stop Loss: 905.10
Take Profit: 927.30
```

---

# Configuration System

```
config.py
```

Central configuration file for strategy and system parameters.

Example configuration:

```
TICKER
TIMEFRAME
EMA_FAST
EMA_SLOW
ATR_PERIOD
RISK_PERCENT
RR
```

This allows quick experimentation without modifying code.

---

# Main Entry Point

```
main.py
```

The main script controls the system execution mode.

Example modes:

```
MODE = "backtest"
MODE = "forward"
MODE = "factor"
```

Based on the mode, the appropriate engine is executed.

---

# Complete Workflow

## Backtesting Mode

```
main.py
   │
   ▼
historical_loader
   │
   ▼
indicators
   │
   ▼
strategy
   │
   ▼
backtest_engine
```

---

## Forward Testing Mode

```
main.py
   │
   ▼
live_data_loader
   │
   ▼
indicators
   │
   ▼
strategy
   │
   ▼
risk model
   │
   ▼
telegram alert
```

---

# Development Roadmap

## Phase 1

Completed:

```
✔ Data layer
✔ EMA calculation
```

---

## Phase 2

Implement indicators:

```
indicators/
    ema.py
    atr.py
```

---

## Phase 3

Develop strategy module:

```
strategies/
    ema_pullback.py
```

---

## Phase 4

Build backtesting engine:

```
backtest/
    backtest_engine.py
```

---

## Phase 5

Add risk management:

```
execution/
    position_sizing.py
```

---

## Phase 6

Build forward testing system:

```
forward_test/
    forward_engine.py
```

---

## Phase 7

Integrate Telegram alert bot:

```
alerts/
    telegram_bot.py
```

---

## Phase 8

Implement factor testing engine:

```
factors/
    factor_engine.py
```

---

# Final System Behavior

Once completed, the system will:

```
1. Fetch live market data
2. Calculate indicators
3. Generate strategy signals
4. Calculate trade risk
5. Send trade alerts to Telegram
```

Example alert:

```
TRADE SIGNAL

Ticker: NVDA
Strategy: EMA Pullback

Entry: 915
Stop Loss: 905
Take Profit: 935

Risk: 1%
R:R ratio : 1:2
```

---

# Future Improvements

Possible enhancements:

* Walk-forward testing
* Portfolio backtesting
* Multi-asset trading
* Multi-timeframe analysis
* Monte Carlo simulation
* Machine learning factors
* Live trade execution

---

# License

MIT License
