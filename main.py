from config import CONFIG
from data.historical_loader import load_historical_data


def main():

    print("Loading historical data...\n")

    df = load_historical_data(
        ticker=CONFIG["TICKER"],
        interval=CONFIG["TIMEFRAME"]
    )

    print("Data Loaded Successfully\n")
    print("Total Rows:", len(df))
    print(df.head(), "\n")

    # ==========================
    # TEST EMA CALCULATION
    # ==========================

    print("Calculating EMAs...\n")

    df["ema_fast"] = df["close"].ewm(
        span=CONFIG["EMA_FAST"],
        adjust=False
    ).mean()

    df["ema_slow"] = df["close"].ewm(
        span=CONFIG["EMA_SLOW"],
        adjust=False
    ).mean()

    print("EMA Calculation Complete\n")

    print(df[["close", "ema_fast", "ema_slow"]].tail())


if __name__ == "__main__":
    main()