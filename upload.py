"""
upload.py  –  Standalone Google Sheets uploader for past backtest runs
=======================================================================

Scans the results/ directory (or a specific run folder you point it at)
and uploads every trades.csv it finds to Google Sheets.

Usage
-----
# Upload everything in results/
python upload.py

# Upload a specific run folder
python upload.py --run results/01_run

# Upload a specific ticker folder inside a run
python upload.py --run results/01_run --ticker nvdl

# Dry-run: show what would be uploaded without actually writing
python upload.py --dry-run

# Upload to a different strategy sheet name (overrides config)
python upload.py --sheet "Strategy Sheet 2 months"
"""

import os
import argparse
import pandas as pd
from config import CONFIG
from upload.tradelogs_update import upload_trade_log_tab, append_strategy_row
from utils.logger import get_logger

log = get_logger("upload")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_strategy_folders(ticker_dir: str) -> list[tuple[str, int | None]]:
    """
    Return a list of (folder_path, strategy_id) for a ticker result folder.

    Handles two layouts:
      • ticker_dir/trades.csv                  → strategy_id = None
      • ticker_dir/strategy 1/trades.csv       → strategy_id = 1
    """
    results = []

    # Direct trades.csv (no strategy sub-folders)
    direct_csv = os.path.join(ticker_dir, "trades.csv")
    if os.path.isfile(direct_csv):
        results.append((ticker_dir, None))
        return results

    # Per-strategy sub-folders
    for entry in sorted(os.listdir(ticker_dir)):
        full = os.path.join(ticker_dir, entry)
        if os.path.isdir(full) and entry.lower().startswith("strategy"):
            csv_path = os.path.join(full, "trades.csv")
            if os.path.isfile(csv_path):
                try:
                    strat_id = int(entry.split()[-1])
                except (ValueError, IndexError):
                    strat_id = None
                results.append((full, strat_id))

    return results


def _find_ticker_dirs(run_dir: str, ticker_filter: str | None = None) -> list[str]:
    """Return all ticker result directories inside a run folder."""
    dirs = []
    for entry in sorted(os.listdir(run_dir)):
        full = os.path.join(run_dir, entry)
        if not os.path.isdir(full):
            continue
        if ticker_filter and not entry.lower().startswith(ticker_filter.lower()):
            continue
        dirs.append(full)
    return dirs


def _find_run_dirs(results_root: str) -> list[str]:
    """Return all *_run directories under results/, sorted numerically."""
    dirs = []
    for entry in sorted(os.listdir(results_root)):
        full = os.path.join(results_root, entry)
        if os.path.isdir(full) and entry.endswith("_run"):
            dirs.append(full)
    return dirs


# ─────────────────────────────────────────────────────────────────────────────
# Core upload logic
# ─────────────────────────────────────────────────────────────────────────────

def upload_strategy_folder(
    strategy_dir: str,
    strategy_id: int | None,
    ticker_folder_name: str,
    config: dict,
    dry_run: bool = False,
) -> None:
    """Upload one strategy folder (trades.csv + trades_summary.txt)."""

    csv_path  = os.path.join(strategy_dir, "trades.csv")
    summ_path = os.path.join(strategy_dir, "trades_summary.txt")

    if not os.path.isfile(csv_path):
        log.warning(f"  ⚠ trades.csv not found in {strategy_dir} – skipped.")
        return

    trades_df = pd.read_csv(csv_path)

    strat_label = f"strategy {strategy_id}" if strategy_id is not None else "no-strategy"
    print(f"    ↳ [{strat_label}]  {len(trades_df)} trades")

    if dry_run:
        print(f"      [DRY RUN] Would upload tab='{ticker_folder_name}', strategy={strategy_id}")
        return

    # Override SINGLE_TICKER from the data so summary row is correct
    if "Ticker" in trades_df.columns and len(trades_df) > 0:
        config = config.copy()
        config["SINGLE_TICKER"] = trades_df["Ticker"].iloc[0]

    upload_trade_log_tab(trades_df, config, tab_name=ticker_folder_name)
    append_strategy_row(
        trades_df, config,
        strategy_id=strategy_id,
        trades_csv_path=csv_path,
        summary_path=summ_path,
    )


def upload_run(
    run_dir: str,
    config: dict,
    ticker_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """Upload all ticker/strategy folders inside a single *_run directory."""

    run_name = os.path.basename(run_dir)
    print(f"\n📁 Run: {run_name}")

    ticker_dirs = _find_ticker_dirs(run_dir, ticker_filter)

    if not ticker_dirs:
        print(f"  ⚠ No ticker folders found in {run_dir}.")
        return

    for ticker_dir in ticker_dirs:
        ticker_folder_name = os.path.basename(ticker_dir)
        print(f"  🗂  {ticker_folder_name}")

        strategy_folders = _find_strategy_folders(ticker_dir)
        if not strategy_folders:
            print(f"    ⚠ No trades.csv found – skipped.")
            continue

        for strategy_dir, strategy_id in strategy_folders:
            upload_strategy_folder(
                strategy_dir, strategy_id,
                ticker_folder_name,
                config,
                dry_run=dry_run,
            )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Upload past backtest runs from results/ to Google Sheets."
    )
    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Path to a specific run folder (e.g. results/01_run). "
             "Omit to process ALL run folders in results/.",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Only upload folders whose name starts with this ticker (case-insensitive). "
             "E.g. --ticker nvdl",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Override STRATEGY_SHEET_NAME from config (e.g. 'Strategy Sheet 2 months').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be uploaded without actually writing to Google Sheets.",
    )
    args = parser.parse_args()

    config = CONFIG.copy()
    config["UPLOAD_TO_SHEETS"] = True   # always True when running this script explicitly

    if args.sheet:
        config["STRATEGY_SHEET_NAME"] = args.sheet

    results_root = config.get("RESULTS_FOLDER", "results")

    if args.dry_run:
        print("\n🔍 DRY RUN – nothing will be written to Google Sheets.\n")

    if args.run:
        # Single run folder specified
        run_dirs = [args.run]
    else:
        # All run folders
        if not os.path.isdir(results_root):
            print(f"❌ Results folder '{results_root}' not found.")
            return
        run_dirs = _find_run_dirs(results_root)
        if not run_dirs:
            print(f"❌ No *_run folders found in '{results_root}'.")
            return

    print(f"\n🚀 Uploading {len(run_dirs)} run(s) to Google Sheets...")
    for run_dir in run_dirs:
        upload_run(run_dir, config, ticker_filter=args.ticker, dry_run=args.dry_run)

    print("\n✅ Upload complete.\n")


if __name__ == "__main__":
    main()
