from config import CONFIG
from data.historical_loader import load_historical_data
from indicators.ema import calculate_ema


def main():

    df = load_historical_data(
        ticker=CONFIG["TICKER"],
        interval=CONFIG["TIMEFRAME"]
    )

    df["ema_fast"] = calculate_ema(df, CONFIG["EMA_FAST"])
    df["ema_slow"] = calculate_ema(df, CONFIG["EMA_SLOW"])

    print(df[["close","ema_fast","ema_slow"]].tail())


if __name__ == "__main__":
    main()