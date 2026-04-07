CONFIG = {

    # ASSET CONFIG
    
    "TICKER":"NVDA",
    "TIMEFRAME": "5m",

    # DATE RANGE (Backtest)
    "START_DATE": "2026-03-01",     
    "END_DATE": "2026-04-06",

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
    "RESULTS_FOLDER": "results",

    # MODES
    "MODE": "forward"  # "backtest" or "forward"
}

# Indian market equity tickers
# "TICKER": "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "LT.NS", "BAJFINANCE.NS", "HINDUNILVR.NS"

# US market equity tickers
# "TICKER": "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "JPM", "V", "MA"


#===================================================================================================================================================================================================================================


# 1. US market chip industries : "NVDA", "AMD", "INTC", "QCOM", "AVGO", "TXN", "MU", "ADI", "LRCX", "AMAT"
# NVDA -> Nvidia
# AMD -> Advanced Micro Devices
# INTC -> Intel
# QCOM -> Qualcomm
# AVGO -> Broadcom
# TXN -> Texas Instruments
# MU -> Micron Technology
# ADI -> Analog Devices
# LRCX -> Lam Research
# AMAT -> Applied Materials



# 2. US market oil and gas tickers : "XOM", "CVX", "LNG", "GLNG", "COP", "EOG", "SLB", "HAL", "OXY", "PXD", "MPC", "PSX"

# XOM -> Exxon Mobil
# LNG -> Cheniere Energy
# GLNG -> Golar LNG
# CVX -> Chevron
# COP -> ConocoPhillips
# EOG -> EOG Resources
# SLB -> Schlumberger
# HAL -> Halliburton
# OXY -> Occidental Petroleum
# PXD -> Pioneer Natural Resources
# MPC -> Marathon Petroleum
# PSX -> Phillips 66


# 3. US market containership tickers : "ZIM", "OSG"
# ZIM -> ZIM Integrated Shipping Services Ltd.
# OSG -> Overseas Shipholding Group, Inc.


