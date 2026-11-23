import pytest
import pandas as pd
import numpy as np
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr
from strategies.ema_pullback import generate_signal, is_green, is_red, is_body_between_emas

def test_deterministic_fixture_structure(sample_ohlcv_df):
    """Verify that sample OHLCV fixture satisfies structural invariants."""
    assert len(sample_ohlcv_df) == 30
    assert list(sample_ohlcv_df.columns) == ["open", "high", "low", "close", "volume"]
    assert (sample_ohlcv_df["high"] >= sample_ohlcv_df["low"]).all()
    assert (sample_ohlcv_df["high"] >= sample_ohlcv_df["open"]).all()
    assert (sample_ohlcv_df["high"] >= sample_ohlcv_df["close"]).all()
    assert (sample_ohlcv_df["low"] <= sample_ohlcv_df["open"]).all()
    assert (sample_ohlcv_df["low"] <= sample_ohlcv_df["close"]).all()

def test_calculate_ema(sample_ohlcv_df):
    """Verify EMA computation returns a series matching DataFrame length and produces non-null values."""
    ema = calculate_ema(sample_ohlcv_df, period=5)
    assert isinstance(ema, pd.Series)
    assert len(ema) == len(sample_ohlcv_df)
    assert not ema.isna().any()
    # In an uptrend, EMA should generally be increasing
    assert ema.iloc[-1] > ema.iloc[0]

def test_calculate_atr(sample_ohlcv_df):
    """Verify ATR computation returns expected length and positive values after rolling warm-up."""
    atr = calculate_atr(sample_ohlcv_df, period=5)
    assert isinstance(atr, pd.Series)
    assert len(atr) == len(sample_ohlcv_df)
    # With TR[0] initialized to high[0] - low[0], rolling(period=5) produces
    # exactly period - 1 (4) NaNs (rows 0 through 3), and first valid ATR is at row index 4.
    assert atr.iloc[:4].isna().all()
    assert (atr.iloc[4:] > 0).all()

def test_candle_helpers():
    """Verify candle coloring and body-between-EMAs helpers."""
    green_candle = {"open": 100.0, "close": 105.0, "ema_fast": 110.0, "ema_slow": 95.0}
    red_candle = {"open": 105.0, "close": 100.0, "ema_fast": 110.0, "ema_slow": 95.0}
    
    assert is_green(green_candle) is True
    assert is_red(green_candle) is False
    assert is_body_between_emas(green_candle) is True
    
    assert is_green(red_candle) is False
    assert is_red(red_candle) is True
    assert is_body_between_emas(red_candle) is True

def test_generate_signal_short_df(sample_ohlcv_df, minimal_config):
    """Verify generate_signal returns None when DataFrame length is less than 5."""
    short_df = sample_ohlcv_df.iloc[:4].copy()
    short_df["ema_fast"] = calculate_ema(short_df, 2)
    short_df["ema_slow"] = calculate_ema(short_df, 3)
    signal = generate_signal(short_df, minimal_config)
    assert signal is None
