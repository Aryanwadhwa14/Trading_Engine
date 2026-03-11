import yfinance as yf
import pandas as pd


def fetch_live_data(ticker="NVDA", interval="1d", lookback="60d"):

    df = yf.download(
        ticker,
        interval=interval,
        period=lookback,
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