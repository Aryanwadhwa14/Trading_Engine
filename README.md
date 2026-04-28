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
| `upload/` | Uploads backtest results (trade logs + summary rows) to Google Sheets |
| `alerts/` | Sends trade signals directly to Telegram |
| `config.py` | Central settings file — change everything from one place |
| `main.py` | Entry point — orchestrates the full pipeline |
| `upload.py` | Standalone CLI to upload past backtest runs to Google Sheets |

Currently active: **EMA Pullback Strategy** with 4 sub-strategies (2 trend + 2 scalp).

---

# Setup

## 1. Install dependencies

This project uses **`uv`** as the package manager. Do **not** use `pip install -r requirements.txt` (it's way to slow bro). The python version is mentioned in `.python-version` file.

```bash
uv sync
```

This reads `pyproject.toml`, resolves the lockfile, and installs all dependencies into the `.venv`.

## 2. Configure environment

Copy `.env.example` to `.env`/`.env.local` and fill in your credentials:

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}   # paste full JSON as one line
```

## 3. Run

Use `uv run` instead of `python` to ensure the correct virtual environment is used:

```bash
uv run main.py                          # uses MODE from config.py
uv run main.py --mode backtest          # force backtest mode
uv run main.py --mode forward           # force forward test mode
uv run main.py --mode backtest --use_multi true   # multi-ticker backtest
uv run upload.py                        # upload past runs to Google Sheets
```

---

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
│   ├── forward_test_engine.py      ← Live paper trading loop
│
├── upload/
│   ├── __init__.py
│   ├── tradelogs_update.py         ← Google Sheets upload logic
│
├── alerts/
│   ├── telegram_bot.py             ← Sends trade signals to Telegram
│
├── utils/
│   ├── market_schedule.py          ← US/India market open/close check
│   ├── logger.py                   ← Centralised loguru logger
│
├── config.py                       ← All settings in one place
├── main.py                         ← Entry point — runs the full pipeline
├── upload.py                       ← Standalone Sheets uploader CLI
└── README.md
```

---

# Core System Flow

```
Market Data  (historical_loader / live_data_loader)
     │
     ▼
Indicators   (ema.py → ema_fast, ema_slow columns)
     │        (atr.py → atr column)
     ▼
Strategy     (ema_pullback.py → signal dict or None)
     │
     ▼
Backtest     (backtest_engine.py → candle-by-candle simulation)
     │
     ▼
Results      (trades.csv + trades_summary.txt per strategy per ticker)
     │
     ▼
Upload       (tradelogs_update.py → Google Sheets trade log tab + strategy row)
```

---

# Configuration System — `config.py`

All system parameters live in one place. Change here — no need to touch strategy or engine code.

```python
from datetime import datetime, timedelta

end_date   = datetime.now()
start_date = end_date - timedelta(days=60)   # rolling 60-day window

CONFIG = {

    # ── ASSET CONFIG ────────────────────────────────────────────────────────
    "USE_MULTI":    True,          # True = multi-ticker run, False = single ticker
    "SINGLE_TICKER": "NVDL",      # used when USE_MULTI = False
    "MULTI_TICKER": [              # full list for multi-ticker runs
        "NVDA", "MSFT", "AAPL", "NVDL", "TQQQ", "TSLA",
        "AMD",  "MU",   "SNDK", "SOXL", "SNXX",
        "JPM",  "V",    "MS",   "AXP",
        "XOM",  "OXY",  "CVX"
    ],
    "TIMEFRAME": "5m",             # candle interval (1m, 5m, 15m, 1h, 1d …)

    # ── DATE RANGE (Backtest) ────────────────────────────────────────────────
    "START_DATE": start_date.strftime("%Y-%m-%d"),
    "END_DATE":   end_date.strftime("%Y-%m-%d"),

    # ── INDICATORS ───────────────────────────────────────────────────────────
    "EMA_FAST":   26,
    "EMA_SLOW":   55,
    "ATR_PERIOD": 14,              # kept for future use
    "INDICATORS": "EMA 26/55",    # label written to trade log & strategy sheet
    "MARKET":     "US",           # written to trade log & strategy sheet

    # ── CAPITAL & RISK ───────────────────────────────────────────────────────
    "INITIAL_BALANCE": 10000,     # starting capital ($)
    "RISK_PERCENT":    0.01,      # 1% risk per trade (future position sizing)

    # ── STRATEGY CONFIG ──────────────────────────────────────────────────────
    "ENABLE_S1": True,            # Trend Long
    "ENABLE_S2": True,            # Trend Short
    "ENABLE_S3": False,           # Scalp Short (Red-Red-Red)
    "ENABLE_S4": False,           # Scalp Long  (Green-Red-Green)
    "TREND_RR":  2.0,             # Risk:Reward for trend trades
    "SCALP_RR":  1.2,             # Risk:Reward for scalp trades

    # ── OUTPUT CONTROL ───────────────────────────────────────────────────────
    "SAVE_RESULTS":   True,
    "RESULTS_FOLDER": "results",

    # ── MODE ─────────────────────────────────────────────────────────────────
    "MODE": "backtest",           # "backtest" or "forward"

    # ── GOOGLE SHEETS UPLOAD ─────────────────────────────────────────────────
    "UPLOAD_TO_SHEETS":   False,  # True = auto-upload after every backtest run
                                  # False = skip (upload manually via upload.py)
    "STRATEGY_SHEET_ID":   "11dMzBHzDPkDgPYgDwdf9xAMu5-9OxtiVlCfJx08Miq0",
    "STRATEGY_SHEET_NAME": "Strategy Sheet 2 months",
    "TRADE_LOG_SHEET_ID":  "1ScmIPXicEoS_Jlk05tYAinPQDGXTd4HmlIuSJZGSfk8",
    "TRADE_LOG_SHEET_NAME": "",   # not used — tab name = folder name at runtime
}
```

### Config quick-reference

| Key | Type | What it controls |
|---|---|---|
| `USE_MULTI` | bool | Single vs multi-ticker mode |
| `SINGLE_TICKER` | str | Ticker when `USE_MULTI = False` |
| `MULTI_TICKER` | list | All tickers for multi-ticker runs |
| `TIMEFRAME` | str | Candle interval passed to yfinance |
| `START_DATE` / `END_DATE` | str | Backtest date window (auto-computed as rolling 60 days) |
| `EMA_FAST` / `EMA_SLOW` | int | EMA periods |
| `INDICATORS` | str | Label written to CSV + Sheets |
| `MARKET` | str | Market label written to CSV + Sheets |
| `INITIAL_BALANCE` | int | Starting capital for PnL calculation |
| `ENABLE_S1..S4` | bool | Toggle individual strategies on/off |
| `TREND_RR` / `SCALP_RR` | float | Risk:Reward multiplier per trade type |
| `MODE` | str | `"backtest"` or `"forward"` |
| `UPLOAD_TO_SHEETS` | bool | Auto-upload to Sheets after backtest |
| `STRATEGY_SHEET_ID` | str | Google Sheet ID for strategy summary |
| `TRADE_LOG_SHEET_ID` | str | Google Sheet ID for raw trade logs |

---

# Running Scripts

## `main.py` — Primary entry point

```bash
# Run using MODE set in config.py
uv run main.py

# Override mode via CLI flag
uv run main.py --mode backtest
uv run main.py --mode forward

# Override multi-ticker toggle
uv run main.py --mode backtest --use_multi true
uv run main.py --mode backtest --use_multi false
```

## `upload.py` — Standalone Google Sheets uploader

Used to manually upload past backtest runs (or selectively upload without rerunning backtests).

```bash
# Upload ALL runs in results/
uv run upload.py

# Upload a specific run folder
uv run upload.py --run results/01_run

# Upload only one ticker from a run
uv run upload.py --run results/01_run --ticker nvdl

# Override the strategy sheet name
uv run upload.py --sheet "Strategy Sheet 2 months"

# Dry-run: see what would be uploaded without writing anything
uv run upload.py --dry-run

# Combine flags
uv run upload.py --run results/01_run --ticker aapl --dry-run
```

---

# Backtesting Engine

```
backtest/
    backtest_engine.py
    backtest_engine.md   ← Full engine documentation
```

The backtesting engine **replays historical data candle by candle** and simulates exactly what would happen if the strategy were live.

### How it works

```
1. Loop through every candle (starting from candle 5)
2. If no position → ask strategy for a signal
3. If signal → enter trade (record entry, SL, TP, units)
4. If LONG → check: low hit SL? high hit TP? last candle of day?
5. If SHORT → check: high hit SL? low hit TP? last candle of day?
6. On any exit → log trade with full details
7. After all candles → compute summary stats
```

### Output structure

Each backtest run creates a numbered folder under `results/`:

```
results/
  01_run/
    nvdl_results(2026-02-28 - 2026-04-29)/
      strategy 1/
        trades.csv            ← every trade, all columns
        trades_summary.txt    ← performance summary
      strategy 2/
        trades.csv
        trades_summary.txt
    aapl_results(2026-02-28 - 2026-04-29)/
      strategy 1/
        ...
  02_run/
    ...
```

### trades.csv schema

| Column | Description |
|---|---|
| Trade Date | Calendar date of trade entry |
| Ticker | Asset symbol |
| Market | Market label (e.g. `US`) |
| Timeframe | Candle interval |
| Side | `LONG` or `SHORT` |
| Trade Type | `TREND` or `SCALP` |
| Strategy No | 1 / 2 / 3 / 4 |
| Indicators | Indicator label (e.g. `EMA 26/55`) |
| Units | Number of shares traded |
| Entry Time | Entry timestamp (PST) |
| Entry Price | Entry price (rounded to 2 dp) |
| Stop Loss | SL price |
| Take Profit | TP price |
| Exit Time | Exit timestamp (PST) |
| Exit Price | Exit price |
| Duration (min) | Trade duration in minutes |
| Entry Reason | Human-readable signal trigger |
| Exit Reason | `SL Hit` / `TP Hit` / `EOD Close` |
| PnL ($) | Dollar profit/loss |
| Return % | % return on entry price |
| Result | `WIN` or `LOSS` |

### Performance metrics (trades_summary.txt)

```
Total Trades    Win Rate       Net Profit
Wins / Losses   Avg Win ($)    Avg Loss ($)
Max Win ($)     Max Loss ($)   Final Balance ($)
Avg Units
```

📄 **See full engine docs:** [`backtest/backtest_engine.md`](backtest/backtest_engine.md)

---

# Google Sheets Upload

The upload system writes results to two separate spreadsheets after a backtest run.

## How it works

```
backtest_engine.py
    │
    ├─ (after each strategy CSV is saved)
    │
    ├── upload_trade_log_tab()    → Trade Log Sheet
    │     tab name = folder name  (e.g. nvdl_results(2026-02-28 - 2026-04-29))
    │     writes: full trades.csv content (header + all rows)
    │
    └── append_strategy_row()    → Strategy Sheet
          finds last filled row → appends one summary row below it
```

## Strategy Sheet columns

| Col | Field | Source |
|---|---|---|
| A | Ticker | trades.csv |
| B | Market | `config["MARKET"]` |
| C | Category | *(blank — fill manually)* |
| D | Type | trades.csv (`Trade Type`) |
| E | Indicators | `config["INDICATORS"]` |
| F | Strategy (Updated) | Strategy number |
| G | Backtest %age | Win rate % |
| H | PnL $ | Net profit |
| I | Return % | Net PnL / initial balance |
| J | Backtesting Trade logs | Local file path to trades.csv |
| K | Backtesting Summary | Local file path to trades_summary.txt |
| L | Paper trading result | *(blank — fill manually)* |
| M | Actual Trading Result | *(blank — fill manually)* |

## Auto-upload toggle

```python
# config.py
"UPLOAD_TO_SHEETS": True    # uploads automatically after every backtest
"UPLOAD_TO_SHEETS": False   # skips — use upload.py to upload manually later
```

## Auth

Reads `GOOGLE_SERVICE_ACCOUNT_JSON` from `.env` as a raw JSON string (service account credentials from Google Cloud Console).

---

# Strategy Layer

```
strategies/
    ema_pullback.py
    ema_strategy.md   ← Full strategy documentation
```

Generates **trade signals only** — never executes anything.

Implements **4 sub-strategies**:

| # | Side | Type | Trigger | RR |
|---|---|---|---|---|
| S1 | LONG | Trend | Candle between EMAs → breaks above EMA Fast | 2.0 |
| S2 | SHORT | Trend | Candle between EMAs → breaks below EMA Fast | 2.0 |
| S3 | SHORT | Scalp | 3 consecutive red candles crossing down through EMAs | 1.2 |
| S4 | LONG | Scalp | Green-Red-Green pattern crossing up through EMAs | 1.2 |

Toggle strategies individually in config:

```python
"ENABLE_S1": True,
"ENABLE_S2": True,
"ENABLE_S3": False,
"ENABLE_S4": False,
```

Signal output:

```python
{
    "signal":      "LONG" / "SHORT",
    "type":        "trend" / "scalp",
    "strategy_id": 1 / 2 / 3 / 4,
    "entry":       price,
    "stop_loss":   price,
    "take_profit": price,
    "reason":      "Prev Candle Between EMAs + Break Above EMA Fast"
}
```

Returns `None` if no setup found.

📄 **See full strategy docs:** [`strategies/ema_strategy.md`](strategies/ema_strategy.md)

---

# Forward Testing Mode (Live)

```
forward_test/
    forward_test_engine.py
```

```bash
uv run main.py --mode forward
```

Runs an infinite loop — fetches live candles every `N` seconds (aligned to the next candle boundary), evaluates the strategy, and fires a Telegram alert if a signal is found.

Key behaviours:
- **Signal deduplication** — hashes signal direction + type + strategy ID + entry price to avoid duplicate alerts within the same candle
- **Latency profiling** — logs fetch/compute/Telegram times to `latency/latency_logs.csv`
- **Error resilience** — broad try/except keeps the loop alive through network hiccups

📄 **See full docs:** [`forward_test/forward_test_engine.md`](forward_test/forward_test_engine.md)

---

# Telegram Alert System — `alerts/telegram_bot.py`

Sends signals to a Telegram chat when the forward test engine fires.

Setup (one-time):
1. Message `@BotFather` → `/newbot` → get `BOT_TOKEN`
2. Send a message to the bot → fetch `CHAT_ID` via `getUpdates`
3. Store both in `.env`

Example alert:

```
TRADE SIGNAL

Ticker:      NVDA
Timeframe:   5m
Strategy:    EMA 26/55 → Strategy 1

Direction:   LONG
Type:        Trend

Entry:       912.50
Stop Loss:   905.10
Take Profit: 927.30
```

---

# Data Layer

## `historical_loader.py`

Downloads OHLCV data via `yfinance`. Returns a standardised DataFrame:

```
datetime (index) | open | high | low | close | volume
```

Rules: index must be datetime, columns must be lowercase, data sorted oldest → newest.

## `live_data_loader.py`

Fetches the most recent candles for forward testing. Same output format as historical loader. Includes sufficient warm-up candles for EMA stability (EMA 55 needs ~200 candles).

---

# Indicator Engine

```
indicators/
    ema.py
    atr.py
```

Columns added to DataFrame:

```
df["ema_fast"]   ← EMA(EMA_FAST)   e.g. EMA 26
df["ema_slow"]   ← EMA(EMA_SLOW)   e.g. EMA 55
df["atr"]        ← ATR(ATR_PERIOD) e.g. ATR 14
```

EMA uses `adjust=False` to match TradingView's standard EMA.

---

# Development Roadmap

| Phase | Module | Status |
|---|---|---|
| 1 | `data/historical_loader.py` | ✅ Done |
| 2 | `indicators/ema.py`, `atr.py` | ✅ Done |
| 3 | `strategies/ema_pullback.py` (S1–S4) | ✅ Done |
| 4 | `backtest/backtest_engine.py` | ✅ Done |
| 5 | `forward_test/forward_test_engine.py` | ✅ Done |
| 6 | `alerts/telegram_bot.py` | ✅ Done |
| 7 | `upload/tradelogs_update.py` + `upload.py` | ✅ Done |

---

# Future Improvements

- Walk-forward testing (avoid overfitting)
- Portfolio backtesting (multiple assets simultaneously)
- Multi-timeframe analysis (daily + 1h confluence)
- Monte Carlo simulation (robustness testing)
- Machine learning signal filters
- Live trade execution via IBKR / Alpaca API
- Link strategy sheet rows to trade log tabs dynamically

---

# License

MIT License
