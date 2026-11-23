import pytest
import pandas as pd
from backtest.backtest_engine import run_backtest

def test_backtest_uses_risk_based_sizing(tmp_path):
    """
    Verify that backtest_engine sizes positions according to RISK_PERCENT
    instead of allocating 100% of available capital.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=10, freq="5min", tz="America/New_York")
    
    # Construct bars designed to trigger Strategy 1 (Trend Long):
    # Uptrend: ema_fast (105) > ema_slow (95)
    # prev1 (bar 6): open=100, close=102 (between 95 and 105)
    # bar 7: close=108 (> ema_fast 105) -> entry=108, sl=ema_slow=95, risk_dist=13
    # bar 8: high=140 -> TP hit
    opens  = [100.0] * 6 + [100.0, 106.0, 108.0, 110.0]
    highs  = [102.0] * 6 + [103.0, 110.0, 140.0, 112.0]
    lows   = [98.0]  * 6 + [99.0,  105.0, 107.0, 105.0]
    closes = [100.0] * 6 + [102.0, 108.0, 135.0, 108.0]
    vols   = [1000]  * 10

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps
    )
    df["ema_fast"] = 105.0
    df["ema_slow"] = 95.0
    df["atr"] = 2.0

    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,  # 1% risk = $100 budget
        "SINGLE_TICKER": "SYNTH",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "TREND_RR": 2.0,
        "SCALP_RR": 1.2,
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
        "INDICATORS": "EMA 26/55",
        "EMA_FAST": 26,
        "EMA_SLOW": 55,
        "MARKET": "US",
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")

    assert len(trades_df) == 1
    trade = trades_df.iloc[0]

    # Entry=108.0, SL=95.0 -> Risk per share = $13.00
    # Risk budget = 10,000 * 0.01 = $100.00
    # Expected units = floor(100 / 13) = 7 units
    # (Under old sizing, units would have been floor(10000 / 108) = 92 units)
    assert trade["Units"] == 7
    assert trade["Risk Budget ($)"] == 100.0
    assert trade["Est Risk ($)"] == 91.0  # 7 * $13
    assert trade["Side"] == "LONG"
    assert trade["Result"] == "WIN"

def test_backtest_rejects_trade_on_insufficient_risk_budget(tmp_path):
    """
    If risk budget is too small to afford even 1 share of risk,
    no trade is executed.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=10, freq="5min", tz="America/New_York")
    opens  = [100.0] * 6 + [100.0, 106.0, 108.0, 110.0]
    highs  = [102.0] * 6 + [103.0, 110.0, 140.0, 112.0]
    lows   = [98.0]  * 6 + [99.0,  105.0, 107.0, 105.0]
    closes = [100.0] * 6 + [102.0, 108.0, 135.0, 108.0]
    vols   = [1000]  * 10

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps
    )
    df["ema_fast"] = 105.0
    df["ema_slow"] = 95.0
    df["atr"] = 2.0

    config = {
        "INITIAL_BALANCE": 500.0,  # small balance
        "RISK_PERCENT": 0.001,    # 0.1% = $0.50 risk budget (cannot afford $13 risk)
        "SINGLE_TICKER": "SYNTH",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "TREND_RR": 2.0,
        "SCALP_RR": 1.2,
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")
    assert len(trades_df) == 0
