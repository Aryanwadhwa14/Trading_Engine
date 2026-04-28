"""
upload/tradelogs_update.py
──────────────────────────
Google Sheets upload logic for the Trading Engine.

Two responsibilities
────────────────────
1. upload_trade_log_tab()
   Writes a trades DataFrame to the Trade Log spreadsheet as a NEW tab
   whose name equals the results-folder name (e.g. nvdl_results(2024-01-01 - 2024-12-31)).
   If the tab already exists it is overwritten (cleared + rewritten).

2. append_strategy_row()
   Reads the last filled row of the Strategy Sheet, then appends one new
   row with the summary metrics for the just-completed backtest run.

Auth
────
Reads GOOGLE_SERVICE_ACCOUNT_JSON from the environment (.env file) as a
raw JSON string, exactly like the reference project pattern.
"""

from __future__ import annotations

import json
import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
log = get_logger("tradelogs_update")

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ─── Strategy Sheet column order (must match the header in the sheet) ────────
_STRATEGY_COLS = [
    "Ticker",
    "Market",
    "Category",           # left blank – skipped on write
    "Type",
    "Indicators",
    "Strategy (Updated)",
    "Backtest %age",
    "PnL $",
    "Return %",
    "Backtesting Trade logs",
    "Backtesting Summary",
    "Paper trading result (forward testing)",   # left blank – skipped on write
    "Actual Trading Result",                    # left blank – skipped on write
]


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

def _get_client() -> gspread.Client:
    """Authenticate using GOOGLE_SERVICE_ACCOUNT_JSON env var (raw JSON string)."""
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set in .env – cannot upload to Google Sheets."
        )
    service_account_info = json.loads(raw)
    creds = Credentials.from_service_account_info(service_account_info, scopes=_SCOPES)
    return gspread.authorize(creds)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Trade Log upload  (new tab per ticker-run)
# ─────────────────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def upload_trade_log_tab(
    trades_df: pd.DataFrame,
    config: dict,
    tab_name: str,
) -> None:
    """
    Write trades_df to the Trade Log Google Sheet as a tab named `tab_name`.

    - If the tab already exists → clear and overwrite.
    - If the tab does not exist → create it.
    - Row 1: column headers
    - Row 2+: data rows

    Parameters
    ----------
    trades_df : pd.DataFrame
        The trade log for one ticker / strategy.
    config : dict
        Must contain TRADE_LOG_SHEET_ID.
    tab_name : str
        Worksheet tab name (= results folder name, e.g. nvdl_results(2024-01-01 - 2024-12-31)).
    """
    sheet_id = config.get("TRADE_LOG_SHEET_ID", "")
    if not sheet_id:
        log.warning("TRADE_LOG_SHEET_ID not set – skipping trade log upload.")
        return

    if trades_df is None or trades_df.empty:
        log.warning(f"[trade log] No trades to upload for tab '{tab_name}'.")
        return

    log.info(f"[trade log] Uploading {len(trades_df)} rows → sheet '{sheet_id}' tab '{tab_name}'")

    client      = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    # Get or create the worksheet
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
        log.info(f"[trade log] Tab '{tab_name}' exists – cleared for overwrite.")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=tab_name,
            rows=str(max(len(trades_df) + 10, 50)),
            cols=str(max(len(trades_df.columns) + 2, 20)),
        )
        log.info(f"[trade log] Created new tab '{tab_name}'.")

    header_row = trades_df.columns.tolist()
    data_rows  = trades_df.astype(str).values.tolist()
    all_rows   = [header_row] + data_rows

    worksheet.update("A1", all_rows)
    log.info(f"[trade log] ✅ Written {len(trades_df)} rows to tab '{tab_name}'.")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Strategy Sheet – append one summary row
# ─────────────────────────────────────────────────────────────────────────────

def _build_strategy_row(
    trades_df: pd.DataFrame,
    config: dict,
    strategy_id=None,
    trades_csv_path: str = "",
    summary_path: str = "",
) -> list:
    """
    Build a single flat list (one row) matching _STRATEGY_COLS order.

    Columns left intentionally blank
    ─────────────────────────────────
    • Category                              (col C)
    • Paper trading result (forward testing) (col L)
    • Actual Trading Result                  (col M)
    """
    initial_balance = config.get("INITIAL_BALANCE", 0)

    if len(trades_df) == 0:
        win_rate   = 0.0
        net_pnl    = 0.0
        return_pct = 0.0
    else:
        wins       = (trades_df["Result"] == "WIN").sum()
        total      = len(trades_df)
        win_rate   = round((wins / total) * 100, 2) if total > 0 else 0.0
        net_pnl    = round(trades_df["PnL ($)"].sum(), 2)
        return_pct = round((net_pnl / initial_balance) * 100, 4) if initial_balance else 0.0

    def _first_col(col, fallback_key=""):
        if col in trades_df.columns and len(trades_df) > 0:
            return str(trades_df[col].iloc[0])
        return str(config.get(fallback_key, ""))

    ticker     = _first_col("Ticker",     "SINGLE_TICKER")
    market     = _first_col("Market",     "MARKET")          # "US" from config
    trade_type = _first_col("Trade Type", "TRADE_TYPE")
    indicators = _first_col("Indicators", "INDICATORS")

    strategy_label = strategy_id if strategy_id is not None else config.get("STRATEGY_LABEL", "")

    # Build row in column order; blanks for Category, L, M
    row = [
        ticker,           # A  Ticker
        market,           # B  Market
        "",               # C  Category  ← intentionally blank
        trade_type,       # D  Type
        indicators,       # E  Indicators
        strategy_label,   # F  Strategy (Updated)
        win_rate,         # G  Backtest %age
        net_pnl,          # H  PnL $
        return_pct,       # I  Return %
        trades_csv_path,  # J  Backtesting Trade logs
        summary_path,     # K  Backtesting Summary
        "",               # L  Paper trading result  ← intentionally blank
        "",               # M  Actual Trading Result  ← intentionally blank
    ]
    return row


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def append_strategy_row(
    trades_df: pd.DataFrame,
    config: dict,
    strategy_id=None,
    trades_csv_path: str = "",
    summary_path: str = "",
) -> None:
    """
    Append one summary row to the Strategy Sheet.

    Reads the last populated row to determine where to write, then
    appends the new row immediately below it.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Full trade log (or per-strategy slice).
    config : dict
        Must contain STRATEGY_SHEET_ID and STRATEGY_SHEET_NAME.
    strategy_id : int | str | None
        Strategy number – written to 'Strategy (Updated)' column.
    trades_csv_path : str
        Path to trades.csv (written to 'Backtesting Trade logs').
    summary_path : str
        Path to trades_summary.txt (written to 'Backtesting Summary').
    """
    sheet_id   = config.get("STRATEGY_SHEET_ID", "")
    sheet_name = config.get("STRATEGY_SHEET_NAME", "")

    if not sheet_id or not sheet_name:
        log.warning("STRATEGY_SHEET_ID or STRATEGY_SHEET_NAME not set – skipping strategy sheet upload.")
        return

    log.info(f"[strategy sheet] Appending row → sheet '{sheet_id}' tab '{sheet_name}'")

    client      = _get_client()
    spreadsheet = client.open_by_key(sheet_id)
    worksheet   = spreadsheet.worksheet(sheet_name)

    # Find the first empty row after the last populated row
    all_values   = worksheet.get_all_values()   # list of lists
    last_row_idx = len(all_values)               # 0-indexed → last used row number (1-indexed = last_row_idx)
    next_row     = last_row_idx + 1              # 1-indexed row to write into

    new_row = _build_strategy_row(
        trades_df, config,
        strategy_id=strategy_id,
        trades_csv_path=trades_csv_path,
        summary_path=summary_path,
    )

    # Write the single row
    col_end    = chr(ord("A") + len(new_row) - 1)  # e.g. "M" for 13 columns
    cell_range = f"A{next_row}:{col_end}{next_row}"
    worksheet.update(cell_range, [new_row])

    log.info(f"[strategy sheet] ✅ Row written at row {next_row} (strategy={strategy_id}).")
