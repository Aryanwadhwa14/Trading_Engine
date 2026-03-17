# Backtest Engine — Full Documentation

**File:** `backtest/backtest_engine.py`  
**Purpose:** Simulates trades on historical price data to test how a strategy would have performed in the real market — without risking any real money.

---

## What Does This File Do?

Think of this file as a **time machine for trading**.

You give it historical price data (e.g., NVDA stock from Sept 2025 to Feb 2026), and it replays every single candle one by one — asking the strategy: *"Should I enter a trade here?"* and *"Should I exit?"*

At the end, it prints a full performance report and saves all trade details to a file.

---

## Imports (Lines 1–4)

```python
import os
import pandas as pd
from datetime import datetime
from strategies.ema_pullback import generate_signal
```

| Import | What it does |
|---|---|
| `os` | Used to create folders and file paths |
| `pandas` | Handles the price data table (DataFrame) |
| `datetime` | Used for timestamps on result folders |
| `generate_signal` | The strategy brain — tells us whether to go LONG, SHORT, or do nothing |

---

## Function 1 — `run_backtest(df, config, start_date, end_date)` *(Lines 7–104)*

### Plain English Explanation

This is the **main engine**. It loops through every candle in the historical data and simulates what would happen if a trader followed the strategy rules exactly.

### What Each Parameter Means

| Parameter | What it is |
|---|---|
| `df` | The full price data table (open, high, low, close + EMA columns) |
| `config` | Settings like ticker name, EMA periods, starting balance |
| `start_date` | When the backtest begins |
| `end_date` | When the backtest ends |

---

### Step-by-Step Walkthrough

#### Setting Up Variables (Lines 9–21)

```python
balance = config.get("INITIAL_BALANCE", 10000)
ticker = config["TICKER"]

position = 0
entry_price = None
...
trade_log = []
```

- **`balance`** — Starting money (default $10,000). This grows or shrinks as trades win/lose.
- **`position`** — Tracks if we're currently in a trade:
  - `0` = no trade open
  - `1` = we are LONG (bought, expecting price to go up)
  - `-1` = we are SHORT (expecting price to go down)
- **`trade_log`** — An empty list where every completed trade gets recorded.

---

#### The Main Loop (Lines 23–88)

```python
for i in range(5, len(df)):
    current_df = df.iloc[:i+1]
    row = df.iloc[i]
```

> **What is this doing?**  
> We start at candle number 5 (not 0) because the strategy needs at least 5 candles of history to make decisions.  
> On each loop, `current_df` is all the candles *up to and including* the current one — like the strategy only knows what's happened so far, not the future.

---

#### Entry Logic (Lines 32–46)

```python
if position == 0:
    signal = generate_signal(current_df)

    if signal:
        position = 1 if signal["signal"] == "LONG" else -1
        entry_price = signal["entry"]
        stop_loss   = signal["stop_loss"]
        take_profit = signal["take_profit"]
        ...
```

> **What is this doing?**  
> If we are not in a trade (`position == 0`), we ask the strategy: *Is there a signal right now?*  
> If yes, we "enter" the trade — storing the entry price, stop loss, and take profit levels.

---

#### Exit Logic — LONG Trade (Lines 49–67)

```python
elif position == 1:
    if low <= stop_loss or high >= take_profit:
        exit_price = stop_loss if low <= stop_loss else take_profit
        pnl = exit_price - entry_price
```

> **What is this doing?**  
> We were LONG (expecting price to go up).  
> - If price dropped **below our stop loss** → we got stopped out (loss)  
> - If price rose **above our take profit** → we won the trade  
>  
> `pnl` (Profit and Loss) = exit price minus entry price.  
> If positive → WIN. If negative → LOSS.

---

#### Exit Logic — SHORT Trade (Lines 70–88)

```python
elif position == -1:
    if high >= stop_loss or low <= take_profit:
        exit_price = stop_loss if high >= stop_loss else take_profit
        pnl = entry_price - exit_price
```

> **What is this doing?**  
> We were SHORT (expecting price to go down).  
> - If price rose **above our stop loss** → loss  
> - If price fell **below our take profit** → win  
>  
> `pnl` = entry price minus exit price (reversed, because shorting profits when price falls).

---

#### Saving Results (Lines 90–104)

```python
trades_df = pd.DataFrame(trade_log)
results_dir = _create_results_folder()

if len(trades_df) > 0:
    trades_df.to_csv(...)

summary = _generate_summary(...)
print(summary)
return trades_df
```

> **What is this doing?**  
> After all candles are processed, it:  
> 1. Converts all trade records into a neat table  
> 2. Creates a timestamped folder (e.g., `results/run_20260317_213000`)  
> 3. Saves a CSV file of every trade  
> 4. Generates and prints a performance summary  

---

## Function 2 — `_log_trade(...)` *(Lines 109–133)*

### Plain English Explanation

Every time a trade closes (either SL hit or TP hit), this function **packages all the details of that trade into a dictionary** (a neat labelled record) that gets added to the `trade_log` list.

### What It Records

| Field | Meaning |
|---|---|
| `Trade Date` | The calendar date the trade was entered |
| `Ticker` | Stock/Asset symbol (e.g., NVDA) |
| `Side` | LONG or SHORT |
| `Trade Type` | trend or scalp |
| `Strategy No` | Which strategy triggered (1, 2, 3, or 4) |
| `Entry Time` | Exact timestamp when we entered |
| `Entry Price` | Price we paid to enter |
| `Stop Loss` | Max loss level we set |
| `Take Profit` | Target profit level we set |
| `Exit Time` | When we exited |
| `Exit Price` | Price at exit |
| `Duration (min)` | How long the trade lasted in minutes |
| `Entry Reason` | Description of what triggered entry (e.g., "Break Above EMA Fast") |
| `Exit Reason` | "SL Hit" or "TP Hit" |
| `PnL ($)` | Dollar profit or loss |
| `Result` | WIN or LOSS |

---

### Code Line Explained

```python
"Duration (min)": int((exit_time - entry_time).total_seconds() / 60),
```

> Subtracts entry time from exit time → gives total seconds → divides by 60 → minutes.  
> Example: 90 seconds = 1.5 minutes → int gives 1 minute.

```python
"Result": "WIN" if pnl > 0 else "LOSS"
```

> If profit is positive → WIN. Otherwise → LOSS. Simple as that.

---

## Function 3 — `_generate_summary(df, balance, config, start_date, end_date)` *(Lines 136–176)*

### Plain English Explanation

After all trades are done, this function **calculates the overall performance stats** and formats them into a readable summary.

Think of it like the end-of-day report a trader would review.

### What It Calculates

```python
wins = len(df[df["Result"] == "WIN"])
losses = len(df[df["Result"] == "LOSS"])
win_rate = (wins / len(df)) * 100
net_profit = df["PnL ($)"].sum()

avg_win  = df[df["Result"] == "WIN"]["PnL ($)"].mean()
avg_loss = df[df["Result"] == "LOSS"]["PnL ($)"].mean()

max_win  = df["PnL ($)"].max()
max_loss = df["PnL ($)"].min()
```

| Metric | What it tells you |
|---|---|
| `wins / losses` | How many trades were profitable vs not |
| `win_rate` | Percentage of trades won — e.g., 60% means 6 out of 10 trades won |
| `net_profit` | Total dollar gain/loss across all trades |
| `avg_win` | On average, how much did each winning trade make? |
| `avg_loss` | On average, how much did each losing trade lose? |
| `max_win` | Biggest single trade win |
| `max_loss` | Biggest single trade loss |

> **No trades check:**
> ```python
> if len(df) == 0:
>     return "No trades."
> ```
> If the strategy didn't generate any signals in the date range, we exit early.

---

## Function 4 — `_create_results_folder()` *(Lines 179–182)*

### Plain English Explanation

Every time you run a backtest, this function **creates a fresh folder** to store the results, so you never overwrite old ones.

```python
def _create_results_folder():
    folder = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder, exist_ok=True)
    return folder
```

> **Example folder created:**  
> `results/run_20260317_213054`  
>  
> The timestamp `%Y%m%d_%H%M%S` means: Year-Month-Day_Hour-Minute-Second.  
> So every run gets a unique folder.  
> `exist_ok=True` means: don't crash if the folder already exists.

---

## Full Data Flow Summary

```
main.py
   │
   ├── loads price data (df)
   ├── calculates EMA & ATR columns
   │
   └── calls run_backtest(df, config, ...)
           │
           ├── loops through every candle
           │       │
           │       ├── no position → ask generate_signal()
           │       │       └── signal? → enter trade
           │       │
           │       ├── LONG position → check SL/TP hit
           │       │       └── hit? → log trade, exit
           │       │
           │       └── SHORT position → check SL/TP hit
           │               └── hit? → log trade, exit
           │
           ├── _log_trade() → packages trade details
           ├── _generate_summary() → calculates stats
           ├── _create_results_folder() → makes timestamped folder
           │
           └── saves trade_log.csv + summary.txt
```

---

## Output Files Explained

| File | What's inside |
|---|---|
| `results/run_YYYYMMDD_HHMMSS/trade_log.csv` | Every single trade with all details |
| `results/run_YYYYMMDD_HHMMSS/summary.txt` | Overall performance metrics printed as text |

---

## Key Concepts for Non-Coders

| Term | Meaning |
|---|---|
| **LONG** | You buy expecting the price to go UP |
| **SHORT** | You sell expecting the price to go DOWN |
| **Stop Loss (SL)** | Your safety net — the trade auto-closes if price hits this to limit losses |
| **Take Profit (TP)** | Your target — the trade auto-closes here to lock in gains |
| **PnL** | Profit and Loss — how much money the trade made or lost |
| **Win Rate** | % of trades that were profitable |
| **DataFrame (df)** | Just a table of price data with rows = candles, columns = open/high/low/close/EMA |
| **Signal** | The strategy's verdict: LONG, SHORT, or nothing |
