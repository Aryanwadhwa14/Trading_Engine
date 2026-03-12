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

    # yfinance returns MultiIndex columns like ("Close", "NVDA") for a single ticker.
    # Flatten to the first level so downstream code gets plain column names.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

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