import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_ohlcv_df():
    """
    Returns a deterministic 30-bar 5-minute OHLCV DataFrame for testing.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=30, freq="5min", tz="America/New_York")
    
    # Deterministic price pattern: modest uptrend with realistic bar shapes
    np.random.seed(42)
    base_price = 100.0
    drift = np.linspace(0, 5, 30)
    
    opens = base_price + drift
    highs = opens + 0.8
    lows = opens - 0.5
    closes = opens + 0.3
    volumes = [1000 + i * 50 for i in range(30)]
    
    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
        index=timestamps,
    )
    df.index.name = "datetime"
    return df

@pytest.fixture
def minimal_config():
    """
    Returns a minimal strategy config dictionary.
    """
    return {
        "ENABLE_S1": True,
        "ENABLE_S2": True,
        "ENABLE_S3": True,
        "ENABLE_S4": True,
        "TREND_RR": 2.0,
        "SCALP_RR": 1.2,
        "EMA_FAST": 5,
        "EMA_SLOW": 10,
        "ATR_PERIOD": 5,
        "INITIAL_BALANCE": 10000,
        "RISK_PERCENT": 0.01,
        "SINGLE_TICKER": "TEST",
        "TIMEFRAME": "5m",
    }

