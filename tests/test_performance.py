import json
import os
import pytest
import pandas as pd
from backtest.performance import (
    compute_drawdown_series,
    compute_performance_metrics,
    compute_strategy_attribution,
    format_portfolio_report,
    get_bars_per_year,
)
from backtest.backtest_engine import run_backtest


def test_drawdown_calculation_and_duration():
    """Verify peak equity, drawdown $, drawdown %, and underwater duration."""
    equity_df = pd.DataFrame({
        "timestamp": pd.date_range("2026-05-01 09:30", periods=6, freq="5min"),
        "equity": [10000.0, 10200.0, 9900.0, 9800.0, 10100.0, 10300.0],
        "in_market": [0, 1, 1, 1, 1, 0],
        "position_value": [0.0, 5000.0, 4900.0, 4800.0, 5100.0, 0.0],
    })
    dd = compute_drawdown_series(equity_df)
    assert list(dd["peak_equity"]) == [10000.0, 10200.0, 10200.0, 10200.0, 10200.0, 10300.0]
    assert dd["drawdown_dollar"].min() == pytest.approx(-400.0)  # 9800 - 10200
    assert dd["drawdown_pct"].min() == pytest.approx((-400.0 / 10200.0) * 100.0)

    metrics, _ = compute_performance_metrics(
        equity_df=equity_df,
        trades_df=pd.DataFrame(),
        initial_balance=10000.0,
        timeframe="5m",
    )
    # Underwater at indices 2, 3, 4 (3 bars)
    assert metrics.max_drawdown_duration_bars == 3
    assert metrics.net_profit == pytest.approx(300.0)
    assert metrics.net_return_pct == pytest.approx(3.0)


def test_unavailable_metrics_marked_none_when_zero_trades():
    """When 0 trades occur, Sharpe, volatility, win rate, profit factor must be None."""
    equity_df = pd.DataFrame({
        "timestamp": pd.date_range("2026-05-01 09:30", periods=5, freq="5min"),
        "equity": [10000.0] * 5,
        "in_market": [0] * 5,
        "position_value": [0.0] * 5,
    })
    bench = pd.Series([100.0, 101.0, 102.0, 101.0, 105.0])
    metrics, _ = compute_performance_metrics(
        equity_df=equity_df,
        trades_df=pd.DataFrame(),
        initial_balance=10000.0,
        timeframe="5m",
        benchmark_close=bench,
    )
    assert metrics.total_trades == 0
    assert metrics.sharpe_ratio is None
    assert metrics.annualized_volatility_pct is None
    assert metrics.win_rate_pct is None
    assert metrics.profit_factor is None
    assert metrics.expectancy_dollar is None
    assert metrics.benchmark_return_pct == pytest.approx(5.0)
    assert metrics.excess_return_pct == pytest.approx(-5.0)

    report = format_portfolio_report(metrics, [], "TEST", "2026-05-01", "2026-05-01")
    assert "Sharpe Ratio:       N/A" in report


def test_trade_quality_and_strategy_attribution():
    """Verify profit factor, expectancy, turnover, and per-strategy attribution."""
    equity_df = pd.DataFrame({
        "timestamp": pd.date_range("2026-05-01 09:30", periods=4, freq="5min"),
        "equity": [10000.0, 10200.0, 10100.0, 10250.0],
        "in_market": [1, 1, 1, 0],
        "position_value": [5000.0, 5200.0, 5100.0, 0.0],
    })
    trades_df = pd.DataFrame([
        {
            "Strategy No": 1, "Units": 10, "Entry Price": 100.0, "Exit Price": 120.0,
            "Gross PnL ($)": 210.0, "Fees ($)": 5.0, "Slippage ($)": 5.0, "PnL ($)": 200.0, "Result": "WIN",
        },
        {
            "Strategy No": 2, "Units": 10, "Entry Price": 100.0, "Exit Price": 90.0,
            "Gross PnL ($)": -90.0, "Fees ($)": 5.0, "Slippage ($)": 5.0, "PnL ($)": -100.0, "Result": "LOSS",
        },
        {
            "Strategy No": 1, "Units": 10, "Entry Price": 100.0, "Exit Price": 115.0,
            "Gross PnL ($)": 160.0, "Fees ($)": 5.0, "Slippage ($)": 5.0, "PnL ($)": 150.0, "Result": "WIN",
        },
    ])
    metrics, _ = compute_performance_metrics(
        equity_df=equity_df,
        trades_df=trades_df,
        initial_balance=10000.0,
        timeframe="5m",
    )
    assert metrics.total_trades == 3
    assert metrics.wins == 2
    assert metrics.losses == 1
    assert metrics.win_rate_pct == pytest.approx(66.67, abs=0.01)
    assert metrics.profit_factor == pytest.approx(3.5)  # 350 / 100
    assert metrics.expectancy_dollar == pytest.approx(250.0 / 3, abs=0.01)
    assert metrics.total_fees_dollar == pytest.approx(15.0)
    assert metrics.total_slippage_dollar == pytest.approx(15.0)
    assert metrics.sharpe_ratio is not None
    assert metrics.annualization_bars_per_year == get_bars_per_year("5m")

    attr = compute_strategy_attribution(trades_df)
    assert len(attr) == 2
    assert attr[0]["strategy_id"] == 1
    assert attr[0]["net_pnl"] == pytest.approx(350.0)
    assert attr[1]["strategy_id"] == 2
    assert attr[1]["net_pnl"] == pytest.approx(-100.0)


def test_backtest_saves_equity_curve_report_and_metadata(tmp_path):
    """Verify run_backtest writes equity_curve.csv, portfolio_summary.txt, and run_metadata.json."""
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
        "COMMISSION_RATE": 0.0005,
        "SLIPPAGE_BPS": 5.0,
        "SINGLE_TICKER": "PERF_TEST",
        "TIMEFRAME": "5m",
        "ENABLE_S1": True,
        "ENABLE_S2": False,
        "ENABLE_S3": False,
        "ENABLE_S4": False,
        "ENTRY_TIMING": "next_bar",
        "SPLIT_LABEL": "validation",
        "UPLOAD_TO_SHEETS": False,
        "RUN_DIR": str(tmp_path),
        "EMA_FAST": 26,
        "EMA_SLOW": 55,
    }

    trades_df = run_backtest(df, config, start_date="2026-05-01", end_date="2026-05-01")
    out_dir = tmp_path / "perf_test_results(2026-05-01 - 2026-05-01)"

    eq_path = out_dir / "equity_curve.csv"
    rep_path = out_dir / "portfolio_summary.txt"
    meta_path = out_dir / "run_metadata.json"

    assert eq_path.is_file()
    assert rep_path.is_file()
    assert meta_path.is_file()

    eq_df = pd.read_csv(eq_path)
    assert len(eq_df) == 5  # bars 5..9
    assert "drawdown_pct" in eq_df.columns
    assert eq_df["equity"].iloc[-1] == pytest.approx(10000.0 + trades_df["PnL ($)"].sum(), abs=0.05)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["split_label"] == "validation"
    assert meta["metrics"]["total_trades"] == 1
    assert len(meta["strategy_attribution"]) == 1

