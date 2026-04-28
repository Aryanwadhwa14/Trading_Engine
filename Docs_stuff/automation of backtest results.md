# Automate Backtest Results to Google Sheets

This plan outlines how to automate the storage of backtest results into Google Sheets. The system will automatically create or update a Google Sheet with the trade logs and performance summaries, separated by strategy, immediately after a backtest finishes.

## User Review Required

> [!IMPORTANT]
> To write data to Google Sheets, you will need to set up a Google Cloud Service Account.
> 1. You will need to create a Service Account in Google Cloud Console and download the JSON key.
> 2. You will need to place that JSON key in the project directory (e.g., as `service_account.json`).
> 3. You will need to create a Google Sheet and **share** it with the email address of the service account so it has editor permissions.

## Open Questions

> [!WARNING]
> 1. Do you already have a Google Cloud Service Account JSON key ready for this, or will you need guidance on creating one?
> 2. Do you want to append new backtest results to the same sheet, or overwrite the sheet with each new run? 

## Proposed Changes

### Configuration
#### [MODIFY] [config.py](file:///d:/Aryan/Trading-engine/config.py)
- Add new settings under `# OUTPUT CONTROL` to enable Google Sheets export and define the target sheet name or ID:
  - `EXPORT_TO_GOOGLE_SHEETS = True`
  - `GOOGLE_SHEET_NAME = "Trading Backtests"`
  - `GOOGLE_SERVICE_ACCOUNT_FILE = "service_account.json"`

### Dependencies
#### [MODIFY] [requirements.txt](file:///d:/Aryan/Trading-engine/requirements.txt)
- Add `gspread` and `google-auth` to manage the Google Sheets API interactions.

### Utilities
#### [NEW] [utils/google_sheets.py](file:///d:/Aryan/Trading-engine/utils/google_sheets.py)
- Create a new utility module to handle authentication and API interactions with Google Sheets.
- Functions to:
  - Authenticate using the service account JSON.
  - Open the target spreadsheet.
  - Create or clear a specific worksheet (tab) for each strategy.
  - Write the `trades_df` (pandas DataFrame) and summary statistics to the worksheets.

### Backtest Engine
#### [MODIFY] [backtest/backtest_engine.py](file:///d:/Aryan/Trading-engine/backtest/backtest_engine.py)
- Import the new Google Sheets utility.
- In the `run_backtest` function, right after the CSV and `.txt` summary files are generated for each strategy, call the utility to upload the `strat_df` and summary text to the respective Google Sheet tabs (e.g., "Strategy 1", "Strategy 2").

## Verification Plan

### Manual Verification
1. Install the new dependencies (`pip install -r requirements.txt`).
2. Run a backtest using `python main.py` with `MODE: "backtest"`.
3. Check the target Google Sheet to verify that tabs have been created for each strategy.
4. Confirm that the trade logs and summary metrics match the local CSV/TXT files.
