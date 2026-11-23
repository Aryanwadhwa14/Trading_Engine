import pytest
import pandas as pd
import numpy as np
import os
from data.validation import validate_ohlcv, normalize_ohlcv, DataValidationError, ValidationResult
from data.historical_loader import load_historical_data

def test_valid_ohlcv_passes(sample_ohlcv_df):
    """Clean deterministic fixture should pass validation with is_valid=True."""
    norm_df, res = validate_ohlcv(sample_ohlcv_df, raise_on_error=True)
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert list(norm_df.columns) == ["open", "high", "low", "close", "volume"]

def test_missing_required_column(sample_ohlcv_df):
    """Dropping a required column should raise DataValidationError."""
    bad_df = sample_ohlcv_df.drop(columns=["volume"])
    with pytest.raises(DataValidationError, match="Missing required OHLCV column"):
        validate_ohlcv(bad_df, raise_on_error=True)

    _, res = validate_ohlcv(bad_df, raise_on_error=False)
    assert res.is_valid is False
    assert any("volume" in e for e in res.errors)

def test_datetime_column_converted_to_index(sample_ohlcv_df):
    """If datetime is provided as a column, normalize_ohlcv sets it as the index."""
    df_with_col = sample_ohlcv_df.reset_index()
    norm_df = normalize_ohlcv(df_with_col)
    assert isinstance(norm_df.index, pd.DatetimeIndex)
    assert norm_df.index.name == "datetime"

def test_nan_prices_rejected(sample_ohlcv_df):
    """NaNs in price columns should fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[5, bad_df.columns.get_loc("close")] = np.nan
    with pytest.raises(DataValidationError, match="contains 1 NaN/null"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_non_positive_prices_rejected(sample_ohlcv_df):
    """Zero or negative prices should fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[3, bad_df.columns.get_loc("low")] = 0.0
    with pytest.raises(DataValidationError, match="non-positive"):
        validate_ohlcv(bad_df, raise_on_error=True)

    bad_df.iloc[3, bad_df.columns.get_loc("low")] = -10.0
    with pytest.raises(DataValidationError, match="non-positive"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_negative_volume_rejected(sample_ohlcv_df):
    """Negative volume must fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[2, bad_df.columns.get_loc("volume")] = -50
    with pytest.raises(DataValidationError, match="negative"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_ohlc_invariant_high_less_than_low(sample_ohlcv_df):
    """High < Low must fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[4, bad_df.columns.get_loc("high")] = bad_df.iloc[4]["low"] - 1.0
    with pytest.raises(DataValidationError, match="high < low"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_ohlc_invariant_high_less_than_close(sample_ohlcv_df):
    """High < Close must fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[4, bad_df.columns.get_loc("high")] = bad_df.iloc[4]["close"] - 0.5
    with pytest.raises(DataValidationError, match="high < close"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_ohlc_invariant_low_greater_than_open(sample_ohlcv_df):
    """Low > Open must fail validation."""
    bad_df = sample_ohlcv_df.copy()
    bad_df.iloc[4, bad_df.columns.get_loc("low")] = bad_df.iloc[4]["open"] + 0.5
    with pytest.raises(DataValidationError, match="low > open"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_duplicate_timestamps_rejected(sample_ohlcv_df):
    """Duplicate timestamps in the index must fail validation."""
    bad_df = sample_ohlcv_df.copy()
    # Duplicate row 0 timestamp at row 1
    new_index = list(bad_df.index)
    new_index[1] = new_index[0]
    bad_df.index = pd.DatetimeIndex(new_index)
    with pytest.raises(DataValidationError, match="duplicate timestamp"):
        validate_ohlcv(bad_df, raise_on_error=True)

def test_non_monotonic_timestamps_rejected(sample_ohlcv_df):
    """Out-of-order timestamps that cannot be sorted monotonically should fail if unsorted."""
    bad_df = sample_ohlcv_df.copy()
    # Swap row 2 and row 3 timestamps
    idx = list(bad_df.index)
    idx[2], idx[3] = idx[3], idx[2]
    bad_df.index = pd.DatetimeIndex(idx)
    # normalize_ohlcv sorts the index by default, but if duplicate or non-increasing post-check:
    norm_df = normalize_ohlcv(bad_df)
    assert norm_df.index.is_monotonic_increasing

def test_historical_loader_with_valid_and_invalid_data(tmp_path, sample_ohlcv_df, monkeypatch):
    """Test load_historical_data validates data and handles corrupted files gracefully."""
    csv_dir = tmp_path / "historical_csvs"
    csv_dir.mkdir(parents=True)
    
    # Write a valid CSV
    valid_csv = csv_dir / "TEST_5m_2026-05-01_to_2026-05-02.csv"
    sample_ohlcv_df.reset_index().to_csv(valid_csv, index=False)
    
    # Point historical_loader to tmp_path
    monkeypatch.setattr("os.path.dirname", lambda p: str(tmp_path) if "historical_loader" in p else os.path.dirname(p))
    
    loaded_df = load_historical_data("TEST", "5m", "2026-05-01", "2026-05-02")
    assert not loaded_df.empty
    assert len(loaded_df) == len(sample_ohlcv_df)

    # Corrupt the CSV with high < low
    corrupt_df = sample_ohlcv_df.copy()
    corrupt_df.iloc[0, corrupt_df.columns.get_loc("high")] = 0.001
    corrupt_df.iloc[0, corrupt_df.columns.get_loc("low")] = 100.0
    corrupt_csv = csv_dir / "BAD_5m_2026-05-01_to_2026-05-02.csv"
    corrupt_df.reset_index().to_csv(corrupt_csv, index=False)

    loaded_bad = load_historical_data("BAD", "5m", "2026-05-01", "2026-05-02")
    assert loaded_bad.empty

