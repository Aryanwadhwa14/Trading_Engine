"""Backtesting and performance analytics package."""
from backtest.backtest_engine import run_backtest
from backtest.performance import (
    PerformanceMetrics,
    build_run_metadata,
    compute_drawdown_series,
    compute_performance_metrics,
    compute_strategy_attribution,
    format_portfolio_report,
)

__all__ = [
    "PerformanceMetrics",
    "build_run_metadata",
    "compute_drawdown_series",
    "compute_performance_metrics",
    "compute_strategy_attribution",
    "format_portfolio_report",
    "run_backtest",
]

