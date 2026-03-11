# file used for loading backtesting data
import yfinance as yf
import pandas as pd


def load_historical_data(ticker="NVDA", interval="1d", period="5y"):

    df = yf.download(
        ticker,
        interval=interval,
        period=period,
        auto_adjust=False
    )

    df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    }, inplace=True)

    df = df[["open", "high", "low", "close", "volume"]]

    df.index.name = "datetime"

    return df