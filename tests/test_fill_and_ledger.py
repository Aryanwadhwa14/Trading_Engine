import pytest
import pandas as pd
from execution.fill_simulator import simulate_entry_fill, simulate_exit_fill
from portfolio.ledger import PortfolioLedger
from backtest.backtest_engine import run_backtest


def test_entry_fill_slippage_and_commission_long_short():
    """Verify adverse slippage direction and commission on LONG and SHORT entries."""
    # LONG: pays 10 bps more
    long_fill = simulate_entry_fill(
        reference_open=100.0,
        quantity=10,
        side="LONG",
        commission_rate=0.001,  # 10 bps
        slippage_bps=10.0,      # 10 bps
    )
    assert long_fill.fill_price == pytest.approx(100.10)
    assert long_fill.slippage_cost == pytest.approx(1.00)  # 0.10 * 10
    assert long_fill.commission == pytest.approx(100.10 * 10 * 0.001)

    # SHORT: sells 10 bps lower
    short_fill = simulate_entry_fill(
        reference_open=100.0,
        quantity=10,
        side="SHORT",
        commission_rate=0.001,
        slippage_bps=10.0,
    )
    assert short_fill.fill_price == pytest.approx(99.90)
    assert short_fill.slippage_cost == pytest.approx(1.00)
    assert short_fill.commission == pytest.approx(99.90 * 10 * 0.001)


def test_exit_fill_gap_through_stop_long_and_short():
    """Gap past stop-loss must fill conservatively at bar open + adverse slippage."""
    # LONG: SL=95, bar opens at 90 (gapped down)
    long_gap = simulate_exit_fill(
        bar_open=90.0, bar_high=92.0, bar_low=89.0, bar_close=91.0,
        quantity=10, side="LONG", stop_loss=95.0, take_profit=110.0,
        is_last_candle=False, commission_rate=0.0005, slippage_bps=10.0,
    )
    assert long_gap is not None
    assert long_gap.exit_reason == "Gap SL"
    assert long_gap.nominal_price == 90.0
    assert long_gap.fill_price == pytest.approx(90.0 * (1 - 0.001))

    # SHORT: SL=105, bar opens at 110 (gapped up)
    short_gap = simulate_exit_fill(
        bar_open=110.0, bar_high=112.0, bar_low=108.0, bar_close=109.0,
        quantity=10, side="SHORT", stop_loss=105.0, take_profit=90.0,
        is_last_candle=False, commission_rate=0.0005, slippage_bps=10.0,
    )
    assert short_gap is not None
    assert short_gap.exit_reason == "Gap SL"
    assert short_gap.nominal_price == 110.0
    assert short_gap.fill_price == pytest.approx(110.0 * (1 + 0.001))


def test_same_bar_stop_target_conflict_uses_stop_first_and_flags_ambiguous():
    """When one bar crosses both SL and TP, stop_first is used and ambiguous_bar=True."""
    fill = simulate_exit_fill(
        bar_open=100.0, bar_high=112.0, bar_low=94.0, bar_close=105.0,
        quantity=10, side="LONG", stop_loss=95.0, take_profit=110.0,
        is_last_candle=False, commission_rate=0.0, slippage_bps=0.0,
        stop_target_conflict="stop_first",
    )
    assert fill is not None
    assert fill.exit_reason == "SL Hit"
    assert fill.nominal_price == 95.0
    assert fill.ambiguous_bar is True


def test_limit_tp_incurs_no_slippage_while_eod_incurs_slippage():
    """Limit TP fills at exact target price; EOD Close applies adverse slippage."""
    tp_fill = simulate_exit_fill(
        bar_open=105.0, bar_high=112.0, bar_low=104.0, bar_close=111.0,
        quantity=10, side="LONG", stop_loss=95.0, take_profit=110.0,
        is_last_candle=True, commission_rate=0.001, slippage_bps=10.0,
    )
    assert tp_fill.exit_reason == "TP Hit"
    assert tp_fill.fill_price == 110.0
    assert tp_fill.slippage_cost == 0.0

    eod_fill = simulate_exit_fill(
        bar_open=102.0, bar_high=104.0, bar_low=101.0, bar_close=103.0,
        quantity=10, side="LONG", stop_loss=95.0, take_profit=110.0,
        is_last_candle=True, commission_rate=0.001, slippage_bps=10.0,
    )
    assert eod_fill.exit_reason == "EOD Close"
    assert eod_fill.fill_price == pytest.approx(103.0 * (1 - 0.001))
    assert eod_fill.slippage_cost > 0.0


def test_ledger_reconciliation_long_and_short():
    """Verify cash, gross P&L, fees, slippage, net P&L, and mark-to-market equity reconcile."""
    ledger = PortfolioLedger(initial_balance=10000.0)

    # 1. LONG round-trip
    entry_long = simulate_entry_fill(100.0, 10, "LONG", commission_rate=0.001, slippage_bps=10.0)
    ledger.open_position(
        symbol="TEST", entry_fill=entry_long, stop_loss=95.0, take_profit=110.0,
        entry_time="t1", signal_time="t0", entry_reason="test", trade_type="trend",
        strategy_id=1, risk_budget=100.0, estimated_risk=50.0,
    )
    # Mark-to-market while open
    assert ledger.mark_to_market_equity(105.0) == pytest.approx(
        ledger.cash + 10 * 105.0
    )

    exit_long = simulate_exit_fill(
        105.0, 111.0, 104.0, 110.0, 10, "LONG", 95.0, 110.0, False,
        commission_rate=0.001, slippage_bps=10.0,
    )
    closed_long = ledger.close_position(exit_long)
    assert closed_long.gross_pnl == pytest.approx(100.0)  # (110 - 100) * 10
    assert closed_long.net_pnl == pytest.approx(
        closed_long.gross_pnl - closed_long.slippage_cost - closed_long.commission_cost
    )
    assert ledger.cash == pytest.approx(10000.0 + ledger.realized_pnl)

    # 2. SHORT round-trip
    entry_short = simulate_entry_fill(100.0, 10, "SHORT", commission_rate=0.001, slippage_bps=10.0)
    ledger.open_position(
        symbol="TEST", entry_fill=entry_short, stop_loss=105.0, take_profit=90.0,
        entry_time="t3", signal_time="t2", entry_reason="test", trade_type="trend",
        strategy_id=2, risk_budget=100.0, estimated_risk=50.0,
    )
    assert ledger.mark_to_market_equity(95.0) == pytest.approx(
        ledger.cash - 10 * 95.0
    )

    exit_short = simulate_exit_fill(
        95.0, 96.0, 89.0, 90.0, 10, "SHORT", 105.0, 90.0, False,
        commission_rate=0.001, slippage_bps=10.0,
    )
    closed_short = ledger.close_position(exit_short)
    assert closed_short.gross_pnl == pytest.approx(100.0)  # (100 - 90) * 10
    assert closed_short.net_pnl == pytest.approx(
        closed_short.gross_pnl - closed_short.slippage_cost - closed_short.commission_cost
    )
    assert ledger.cash == pytest.approx(10000.0 + ledger.realized_pnl)


def test_backtest_with_costs_reconciles_gross_and_net_pnl(tmp_path):
    """Run full backtest with non-zero commission and slippage and verify net P&L reconciliation."""
    timestamps = pd.date_range("2026-05-01 09:30:00", periods=10, freq="5min", tz="America/New_York")
    opens  = [100.0] * 6 + [100.0, 106.0, 108.0, 110.0]
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
        "COMMISSION_RATE": 0.001,   # 10 bps
        "SLIPPAGE_BPS": 10.0,       # 10 bps
        "SINGLE_TICKER": "COST_TEST",
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
    row = trades_df.iloc[0]

    assert row["Fees ($)"] > 0
    assert row["Slippage ($)"] > 0
    assert row["Gross PnL ($)"] > row["PnL ($)"]
    assert row["PnL ($)"] == pytest.approx(
        row["Gross PnL ($)"] - row["Fees ($)"] - row["Slippage ($)"],
        abs=0.02,
    )

