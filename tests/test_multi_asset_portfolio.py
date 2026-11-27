import pytest
import pandas as pd
from risk.portfolio_limits import PortfolioRiskConfig, check_portfolio_limits
from portfolio.ledger import PortfolioLedger
from execution.fill_simulator import simulate_entry_fill, simulate_exit_fill
from backtest.event_loop import run_portfolio_backtest
from backtest.backtest_engine import run_backtest


def _make_s1_df(start_ts: str = "2026-05-01 09:30:00", periods: int = 10, price_offset: float = 0.0) -> pd.DataFrame:
    """Helper producing a deterministic 10-bar DataFrame that triggers S1 at bar 7 and TP at bar 8."""
    timestamps = pd.date_range(start_ts, periods=periods, freq="5min", tz="America/New_York")
    opens  = [100.0 + price_offset] * 6 + [100.0 + price_offset, 106.0 + price_offset, 108.0 + price_offset, 110.0 + price_offset]
    highs  = [102.0 + price_offset] * 6 + [103.0 + price_offset, 110.0 + price_offset, 140.0 + price_offset, 112.0 + price_offset]
    lows   = [98.0 + price_offset]  * 6 + [99.0 + price_offset,  105.0 + price_offset, 107.0 + price_offset, 105.0 + price_offset]
    closes = [100.0 + price_offset] * 6 + [102.0 + price_offset, 108.0 + price_offset, 135.0 + price_offset, 108.0 + price_offset]
    vols   = [1000] * periods

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=timestamps,
    )
    df["ema_fast"] = 105.0 + price_offset
    df["ema_slow"] = 95.0 + price_offset
    df["atr"] = 2.0
    return df


def test_portfolio_limits_gates():
    """Verify max open positions, gross exposure, symbol exposure, and daily loss halt."""
    limits = PortfolioRiskConfig(
        max_open_positions=2,
        max_gross_exposure=0.80,
        max_symbol_exposure=0.50,
        max_daily_loss_pct=0.02,
    )

    # Normal approval
    dec = check_portfolio_limits(
        symbol="NVDA", current_equity=10000.0, day_start_equity=10000.0,
        peak_equity=10000.0, open_positions_count=1, has_symbol_position=False,
        current_gross_exposure=4000.0, limits=limits,
    )
    assert dec.is_approved is True
    # Remaining gross = 8000 - 4000 = 4000; symbol cap = 5000 -> min(4000, 5000) = 4000
    assert dec.max_allowed_notional == pytest.approx(4000.0)

    # Max open positions reached
    dec_max = check_portfolio_limits(
        symbol="MSFT", current_equity=10000.0, day_start_equity=10000.0,
        peak_equity=10000.0, open_positions_count=2, has_symbol_position=False,
        current_gross_exposure=4000.0, limits=limits,
    )
    assert dec_max.is_approved is False
    assert "Max open positions" in dec_max.rejection_reason

    # Daily loss halt (equity dropped 2.5% from day start)
    dec_halt = check_portfolio_limits(
        symbol="MSFT", current_equity=9750.0, day_start_equity=10000.0,
        peak_equity=10000.0, open_positions_count=0, has_symbol_position=False,
        current_gross_exposure=0.0, limits=limits,
    )
    assert dec_halt.is_approved is False
    assert "Daily loss halt" in dec_halt.rejection_reason


def test_multi_asset_ledger_reconciliation():
    """Verify simultaneous LONG + SHORT positions share cash and reconcile equity."""
    ledger = PortfolioLedger(initial_balance=10000.0)

    f_long = simulate_entry_fill(100.0, 10, "LONG", commission_rate=0.001, slippage_bps=0.0)
    f_short = simulate_entry_fill(50.0, 20, "SHORT", commission_rate=0.001, slippage_bps=0.0)

    ledger.open_position(
        "AAPL", f_long, 95.0, 110.0, "t1", "t0", "test", "trend", 1, 100.0, 50.0
    )
    ledger.open_position(
        "TSLA", f_short, 55.0, 40.0, "t1", "t0", "test", "trend", 2, 100.0, 100.0
    )
    assert ledger.open_position_count == 2

    # Mark-to-market: AAPL @ 105 (+50), TSLA @ 45 (+100), minus $2 entry fees
    eq = ledger.mark_to_market_equity({"AAPL": 105.0, "TSLA": 45.0})
    assert eq == pytest.approx(10000.0 + 50.0 + 100.0 - 2.0)

    e_long = simulate_exit_fill(105.0, 110.0, 104.0, 110.0, 10, "LONG", 95.0, 110.0, False, commission_rate=0.001)
    e_short = simulate_exit_fill(45.0, 46.0, 40.0, 40.0, 20, "SHORT", 55.0, 40.0, False, commission_rate=0.001)

    ledger.close_position(e_long, symbol="AAPL")
    ledger.close_position(e_short, symbol="TSLA")

    assert ledger.is_flat
    assert ledger.cash == pytest.approx(10000.0 + ledger.realized_pnl)


def test_shared_portfolio_enforces_max_positions_and_no_double_spending(tmp_path):
    """When AAPL and NVDA signal simultaneously, MAX_OPEN_POSITIONS=1 permits only AAPL (alphabetical)."""
    data = {
        "NVDA": _make_s1_df(),
        "AAPL": _make_s1_df(),
    }
    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "MAX_OPEN_POSITIONS": 1,
        "MAX_GROSS_EXPOSURE": 0.80,
        "MAX_SYMBOL_EXPOSURE": 0.80,
        "MAX_DAILY_LOSS": 0.05,
        "COMMISSION_RATE": 0.0005,
        "SLIPPAGE_BPS": 5.0,
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

    trades_df, eq_df, meta = run_portfolio_backtest(data, config, "2026-05-01", "2026-05-01")
    # Only 1 trade executed because MAX_OPEN_POSITIONS=1 and AAPL comes before NVDA
    assert len(trades_df) == 1
    assert trades_df.iloc[0]["Ticker"] == "AAPL"
    assert eq_df["equity"].iloc[-1] == pytest.approx(10000.0 + trades_df["PnL ($)"].sum(), abs=0.05)


def test_shared_portfolio_handles_unaligned_timestamps_without_ffill(tmp_path):
    """Symbols with non-overlapping or missing bars execute cleanly on their own timestamps."""
    df_aapl = _make_s1_df("2026-05-01 09:30:00")
    # Drop bar 8 on NVDA? No, shift NVDA by 1 hour so bars don't overlap identically
    df_nvda = _make_s1_df("2026-05-01 10:30:00")

    data = {"AAPL": df_aapl, "NVDA": df_nvda}
    config = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "MAX_OPEN_POSITIONS": 2,
        "MAX_GROSS_EXPOSURE": 0.80,
        "MAX_SYMBOL_EXPOSURE": 0.50,
        "MAX_DAILY_LOSS": 0.05,
        "COMMISSION_RATE": 0.0,
        "SLIPPAGE_BPS": 0.0,
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

    trades_df, eq_df, _ = run_portfolio_backtest(data, config, "2026-05-01", "2026-05-01")
    assert len(trades_df) == 2
    assert set(trades_df["Ticker"]) == {"AAPL", "NVDA"}
    assert eq_df["equity"].iloc[-1] == pytest.approx(10000.0 + trades_df["PnL ($)"].sum(), abs=0.05)


def test_single_symbol_regression_matches_single_engine(tmp_path):
    """Single-symbol run_portfolio_backtest matches run_backtest PnL and trade count."""
    df = _make_s1_df()
    cfg = {
        "INITIAL_BALANCE": 10000.0,
        "RISK_PERCENT": 0.01,
        "MAX_OPEN_POSITIONS": 1,
        "MAX_GROSS_EXPOSURE": 1.0,
        "MAX_SYMBOL_EXPOSURE": 1.0,
        "MAX_DAILY_LOSS": 0.50,
        "COMMISSION_RATE": 0.0005,
        "SLIPPAGE_BPS": 5.0,
        "SINGLE_TICKER": "SYNTH",
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

    single_trades = run_backtest(df, cfg.copy(), "2026-05-01", "2026-05-01")
    port_trades, _, _ = run_portfolio_backtest({"SYNTH": df}, cfg.copy(), "2026-05-01", "2026-05-01")

    assert len(single_trades) == len(port_trades) == 1
    assert single_trades.iloc[0]["Units"] == port_trades.iloc[0]["Units"]
    assert single_trades.iloc[0]["PnL ($)"] == pytest.approx(port_trades.iloc[0]["PnL ($)"], abs=0.01)

