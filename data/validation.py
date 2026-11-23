"""
data/validation.py
──────────────────
Data validation and normalization for canonical OHLCV market data.

Enforces strict data integrity invariants:
1. Canonical schema: required columns [open, high, low, close, volume] in lowercase.
2. Datetime index: sorted strictly ascending, monotonic increasing, unique (no duplicates).
3. Cleanliness: no NaN, null, or infinite values in OHLCV columns.
4. Positive prices: open > 0, high > 0, low > 0, close > 0.
5. Non-negative volume: volume >= 0.
6. OHLC invariants:
   - high >= low
   - high >= max(open, close)
   - low <= min(open, close)
7. Missing-data policy: Never silently forward-fill tradable prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    """Raised when market data violates required structural or financial invariants."""
    pass


@dataclass
class ValidationResult:
    """Detailed summary of data validation checks."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


REQUIRED_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize DataFrame to canonical OHLCV representation:
    - Lowercase column names with whitespace stripped
    - Ensure datetime index is a valid DatetimeIndex and sorted
    - Ensure standard numeric types for OHLCV columns
    """
    if df is None or df.empty:
        raise DataValidationError("Input DataFrame is empty or None.")

    clean_df = df.copy()

    # If datetime is a column instead of index, convert and set as index
    if "datetime" in [str(c).strip().lower() for c in clean_df.columns]:
        dt_col = [c for c in clean_df.columns if str(c).strip().lower() == "datetime"][0]
        clean_df[dt_col] = pd.to_datetime(clean_df[dt_col])
        clean_df.set_index(dt_col, inplace=True)
        clean_df.index.name = "datetime"
    elif not isinstance(clean_df.index, pd.DatetimeIndex):
        try:
            clean_df.index = pd.to_datetime(clean_df.index)
            clean_df.index.name = "datetime"
        except Exception as e:
            raise DataValidationError(f"Index could not be converted to DatetimeIndex: {e}")

    # Standardize column names
    clean_df.columns = [str(c).strip().lower() for c in clean_df.columns]

    # Check for missing required columns
    missing = [c for c in REQUIRED_OHLCV_COLUMNS if c not in clean_df.columns]
    if missing:
        raise DataValidationError(
            f"Missing required OHLCV column(s): {missing}. Available: {list(clean_df.columns)}"
        )

    # Convert OHLCV columns to numeric
    for col in REQUIRED_OHLCV_COLUMNS:
        clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")

    # Sort index chronologically
    clean_df = clean_df.sort_index()

    return clean_df


def validate_ohlcv(
    df: pd.DataFrame,
    raise_on_error: bool = True,
    timeframe: str | None = None,
) -> tuple[pd.DataFrame, ValidationResult]:
    """
    Validate a market data DataFrame against canonical OHLCV invariants.

    Parameters
    ----------
    df : pd.DataFrame
        Input price data.
    raise_on_error : bool, default True
        If True, raises DataValidationError upon encountering any failure.
    timeframe : str, optional
        Timeframe identifier (e.g. '5m') for context in diagnostics.

    Returns
    -------
    tuple[pd.DataFrame, ValidationResult]
        Normalized DataFrame and the structured validation result.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. Structural Normalization ────────────────────────────────────────
    try:
        norm_df = normalize_ohlcv(df)
    except DataValidationError as e:
        if raise_on_error:
            raise
        return df, ValidationResult(is_valid=False, errors=[str(e)])

    # ── 2. Datetime Index Checks ───────────────────────────────────────────
    if not norm_df.index.is_monotonic_increasing:
        errors.append("Timestamps are not in strictly monotonic ascending order.")

    duplicates = norm_df.index.duplicated(keep="first")
    dup_count = int(np.sum(duplicates))
    if dup_count > 0:
        dup_sample = norm_df.index[duplicates][:3].tolist()
        errors.append(f"Found {dup_count} duplicate timestamp(s). Sample: {dup_sample}")

    if norm_df.index.tz is None:
        warnings.append("DatetimeIndex is timezone-naive. UTC or local timezone recommended.")

    # ── 3. Null / NaN / Inf Checks ─────────────────────────────────────────
    for col in REQUIRED_OHLCV_COLUMNS:
        null_count = int(norm_df[col].isna().sum())
        if null_count > 0:
            errors.append(f"Column '{col}' contains {null_count} NaN/null value(s).")

        inf_count = int(np.isinf(norm_df[col]).sum())
        if inf_count > 0:
            errors.append(f"Column '{col}' contains {inf_count} infinite value(s).")

    # If nulls exist, skip numeric relational checks on those rows
    if not any("NaN" in e or "null" in e for e in errors):
        # ── 4. Price Positivity & Volume Non-Negativity ────────────────────
        for col in ["open", "high", "low", "close"]:
            non_positive = (norm_df[col] <= 0).sum()
            if non_positive > 0:
                errors.append(f"Column '{col}' has {non_positive} non-positive (<= 0) price(s).")

        negative_vol = (norm_df["volume"] < 0).sum()
        if negative_vol > 0:
            errors.append(f"Column 'volume' has {negative_vol} negative (< 0) value(s).")

        # ── 5. OHLC Mathematical Invariants ────────────────────────────────
        # high >= low
        hl_violations = (norm_df["high"] < norm_df["low"]).sum()
        if hl_violations > 0:
            errors.append(f"OHLC invariant violated: high < low in {hl_violations} row(s).")

        # high >= open
        ho_violations = (norm_df["high"] < norm_df["open"]).sum()
        if ho_violations > 0:
            errors.append(f"OHLC invariant violated: high < open in {ho_violations} row(s).")

        # high >= close
        hc_violations = (norm_df["high"] < norm_df["close"]).sum()
        if hc_violations > 0:
            errors.append(f"OHLC invariant violated: high < close in {hc_violations} row(s).")

        # low <= open
        lo_violations = (norm_df["low"] > norm_df["open"]).sum()
        if lo_violations > 0:
            errors.append(f"OHLC invariant violated: low > open in {lo_violations} row(s).")

        # low <= close
        lc_violations = (norm_df["low"] > norm_df["close"]).sum()
        if lc_violations > 0:
            errors.append(f"OHLC invariant violated: low > close in {lc_violations} row(s).")

    is_valid = len(errors) == 0

    if not is_valid and raise_on_error:
        context = f" for timeframe '{timeframe}'" if timeframe else ""
        formatted_errs = "\n - ".join(errors)
        raise DataValidationError(f"Market data validation failed{context}:\n - {formatted_errs}")

    return norm_df, ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

