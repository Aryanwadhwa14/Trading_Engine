import pytest
import pandas as pd
from strategies.base import Signal
from strategies.ema_pullback import generate_signal
from backtest.backtest_engine import run_backtest


def test_signal_model_validations():
    """Verify Signal model enforces invariants and causal timestamp order."""
    t0 = pd.Timestamp("2026-05-01 09:30:00")
    t1 = pd.Timestamp("2026-05-01 09:35:00")

    # Valid signal
    sig = Signal(
        symbol="TEST",
        side="LONG",
        strategy_id=1,
        signal_type="trend",
        signal_time=t0,
        available_at=t1,
        reference_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        timeframe="5m",
        reason="Trend test",
    )
    assert sig.entry == 100.0
    assert sig["entry"] == 100.0
    assert sig["signal"] == "LONG"
    assert sig["stop_loss"] == 95.0
    assert sig.available_at == t1

    # available_at before signal_time must fail
    with pytest.raises(ValueError, match="available_at.*cannot precede"):
        Signal(
            symbol="TEST",
            side="LONG",
            strategy_id=1,
            signal_type="trend",
            signal_time=t1,
            available_at=t0,
            reference_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="5m",
            reason="Bad timestamps",
        )

    # Invalid stop direction for LONG
    with pytest.raises(ValueError, match="must be below reference_price"):
        Signal(
            symbol="TEST",
            side="LONG",
            strategy_id=1,
            signal_type="trend",
            signal_time=t0,
            available_at=t1,
            reference_price=100.0,
            stop_loss=105.0,
            take_profit=110.0,
            timeframe="5m",
            reason="Bad stop",
        )


def test_causal_next_bar_execution(tmp_path):
    """
    Verify that with entry_timing='next_bar':
    1. Signal confirmed at close of candle t enters on candle t+1 at open price.
    2. Trade log records both Signal Time and Entry Time.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=10, freq="5min", tz="America/New_York")

    # Strategy 1 trigger at Bar 7 (10:05):
    # Bar 6 (10:00): open=100, close=102 (between EMAs 95 and 105)
    # Bar 7 (10:05): close=108 (> EMA fast 105) -> Signal confirmed at 10:05!
    # Bar 8 (10:10): open=109.0, high=140.0 -> Enters at open=109.0, then hits TP!
    opens  = [100.0] * 6 + [100.0, 106.0, 109.0, 110.0]
    highs  = [102.0] * 6 + [103.0, 110.0, 140.0, 112.0]
    lows   = [98.0]  * 6 + [99.0,  105.0, 107.0, 105.0]
    closes = [100.0] * 6 + [102.0, 108.0, 135.0, 108.0]
    vols   = [1000]  * 10

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps,
    )
    df["ema_fast"] = 105.0
    df["ema_slow"] = 95.0
    df["atr"] = 2.0

    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "SINGLE_TICKER": "CAUSAL_TEST",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "ENTRY_TIMING": "next_bar",
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
        "EMA_FAST": 26,
        "EMA_SLOW": 55,
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")
    assert len(trades_df) == 1
    trade = trades_df.iloc[0]

    # Entry must be at Bar 8 open (109.0), NOT Bar 7 close (108.0) or Bar 7 open (106.0)
    assert trade["Entry Price"] == 109.0

    # Signal Time is Bar 7 (07:05 PST / 10:05 EST), Entry Time is Bar 8 (07:10 PST / 10:10 EST)
    assert "07:05:00" in trade["Signal Time"]
    assert "07:10:00" in trade["Entry Time"]


def test_signal_on_final_bar_does_not_fill(tmp_path):
    """
    If a signal triggers on the last bar of the dataset, it cannot execute
    because no next-bar exists. It must not time-travel.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=8, freq="5min", tz="America/New_York")

    # Bar 7 is the final bar where signal triggers
    opens  = [100.0] * 6 + [100.0, 106.0]
    highs  = [102.0] * 6 + [103.0, 110.0]
    lows   = [98.0]  * 6 + [99.0,  105.0]
    closes = [100.0] * 6 + [102.0, 108.0]
    vols   = [1000]  * 8

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps,
    )
    df["ema_fast"] = 105.0
    df["ema_slow"] = 95.0
    df["atr"] = 2.0

    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "SINGLE_TICKER": "FINAL_BAR_TEST",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "ENTRY_TIMING": "next_bar",
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
        "EMA_FAST": 26,
        "EMA_SLOW": 55,
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")
    # Signal could not fill because dataset ended at candle 7
    assert len(trades_df) == 0


def test_gap_past_stop_loss_rejected_at_next_bar_open(tmp_path):
    """
    If the next bar opens below the stop loss (gap-down),
    risk manager vetoes the order at execution time.
    """
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=10, freq="5min", tz="America/New_York")

    # Bar 7 triggers Long with SL=95.0
    # Bar 8 opens at 90.0 (gapped below SL 95.0)
    opens  = [100.0] * 6 + [100.0, 106.0, 90.0,  92.0]
    highs  = [102.0] * 6 + [103.0, 110.0, 94.0,  95.0]
    lows   = [98.0]  * 6 + [99.0,  105.0, 88.0,  90.0]
    closes = [100.0] * 6 + [102.0, 108.0, 92.0,  93.0]
    vols   = [1000]  * 10

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps,
    )
    df["ema_fast"] = 105.0
    df["ema_slow"] = 95.0
    df["atr"] = 2.0

    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "SINGLE_TICKER": "GAP_TEST",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "ENTRY_TIMING": "next_bar",
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
        "EMA_FAST": 26,
        "EMA_SLOW": 55,
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")
    # Rejected because entry (90.0) <= SL (95.0)
    assert len(trades_df) == 0


def test_indicator_warmup_prevents_premature_signals(sample_ohlcv_df, minimal_config):
    """If indicators are NaN on latest candle, generate_signal returns None."""
    df = sample_ohlcv_df.copy()
    df["ema_fast"] = float("nan")
    df["ema_slow"] = 100.0
    signal = generate_signal(df, minimal_config)
    assert signal is None

