from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=30)

CONFIG = {

    # ASSET CONFIG
    "USE_MULTI": False,  # True for multi ticker, False for single ticker
    "SINGLE_TICKER": "NVDA", # single ticker for both backtest & forward test 
    
    "MULTI_TICKER": ["MSFT", "AAPL","NVDL", "TQQQ", "TSLA", "AMD", "MU", "SNDK", "SOXL", "SNXX","JPM","V","MS","AXP","XOM","OXY","CVX"]                                   , # multi for backtest & forward test 
    "TIMEFRAME": "5m",

    
    # DATE RANGE (Backtest)
    "START_DATE": start_date.strftime("%Y-%m-%d"),     
    "END_DATE": end_date.strftime("%Y-%m-%d"),

    # INDICATORS
    "EMA_FAST": 26,
    "EMA_SLOW": 55,
    "ATR_PERIOD": 14,   # (kept for future use)
    "INDICATORS": "EMA 26/55",
    "MARKET": "US",

    # CAPITAL & RISK
    "INITIAL_BALANCE": 10000,
    "RISK_PERCENT": 0.01,   # 1% equity risk per trade
    "MAX_OPEN_POSITIONS": 3,
    "MAX_GROSS_EXPOSURE": 0.80,
    "MAX_SYMBOL_EXPOSURE": 0.50,
    "MAX_DAILY_LOSS": 0.02,

    # EXECUTION & COSTS
    "COMMISSION_RATE": 0.0005,          # 0.05% (5 bps) commission per side
    "SLIPPAGE_BPS": 5.0,                # 5 bps adverse slippage on market/stop/EOD fills
    "ENTRY_TIMING": "next_bar",         # "next_bar" (causal) or "same_bar" (legacy)
    "STOP_TARGET_CONFLICT": "stop_first",
    "CLOSE_POSITIONS_AT_END": True,

    # STRATEGY CONFIG
    "ENABLE_S1": True,
    "ENABLE_S2": True,
    "ENABLE_S3": True,
    "ENABLE_S4": True,
    "TREND_RR": 2.0,    # Trend trades RR
    "SCALP_RR": 1.2,    # Scalp trades RR

    # # BACKTEST CONTROL
    # "MAX_TRADES": 10000,

    # OUTPUT CONTROL
    "SAVE_RESULTS": True,
    "RESULTS_FOLDER": "results",

    # MODES
    "MODE": "backtest",  # "backtest" or "forward"

    # Google Sheet upload
    "UPLOAD_TO_SHEETS": True,           # set False to skip auto-upload after backtest
    "STRATEGY_SHEET_ID": "1nmjelTU6o6UXr4qgz4e8Fl5pohu4KCM5sc2X1u11N_U",
    "STRATEGY_SHEET_NAME": "trade sheets",
    
    "TRADE_LOG_SHEET_ID": "1Wi7hw90YozkdMSiS0K_u7UaAjFPsa6t6RrWN0MAmRYo",
    "TRADE_LOG_SHEET_NAME": "Trade logs"
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

# 4. Banks and finance tickers : "JPM","V","MS","AXP","BAC","WFC","GS","MS","C","USB"
# JPM -> JPMorgan Chase & Co.
# V -> Visa Inc.
# MS -> Morgan Stanley
# AXP -> American Express Company
# BAC -> Bank of America Corporation
# WFC -> Wells Fargo & Company  
# GS -> Goldman Sachs Group, Inc.
# C -> Citigroup Inc.
# USB -> U.S. Bancorp