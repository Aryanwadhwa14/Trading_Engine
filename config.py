CONFIG = {

    # ASSET CONFIG
    "TICKER": "AAPL",
    "TIMEFRAME": "1d",

    # DATE RANGE (Backtest)
    "START_DATE": "2025-09-01",
    "END_DATE": "2026-02-17",

    # INDICATORS
    "EMA_FAST": 26,
    "EMA_SLOW": 55,
    "ATR_PERIOD": 14,   # (kept for future use)

    # CAPITAL & RISK
    "INITIAL_BALANCE": 10000,
    "RISK_PERCENT": 0.01,   # not yet used fully (future position sizing)

    # STRATEGY CONFIG
    "TREND_RR": 2.0,    # Trend trades RR
    "SCALP_RR": 1.2,    # Scalp trades RR

    # BACKTEST CONTROL
    "MAX_TRADES": 10000,

    # OUTPUT CONTROL
    "SAVE_RESULTS": True,
    "RESULTS_FOLDER": "results"
}
