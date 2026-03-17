from config import CONFIG
from data.historical_loader import load_historical_data
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr
from strategies.ema_pullback import generate_signal

def main():

    df = load_historical_data(
        ticker=CONFIG["TICKER"],
        interval=CONFIG["TIMEFRAME"]
    )

    print("Calculating Indicators-> ")

    df["ema_fast"] = calculate_ema(df, CONFIG["EMA_FAST"])
    df["ema_slow"] = calculate_ema(df, CONFIG["EMA_SLOW"])
    df["atr"] = calculate_atr(df, CONFIG["ATR_PERIOD"])

    signal = generate_signal(df)

    if signal : 
        print("Signal detected")
        print(signal)
    else : 
        print("No signal detected")

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    print("\nDEBUG INFO")
    print("Close:", latest["close"])
    print("Open:", latest["open"])
    print("EMA FAST:", latest["ema_fast"])
    print("EMA SLOW:", latest["ema_slow"])
    print("\nTrend:",
      "UPTREND" if latest["ema_fast"] > latest["ema_slow"] else "DOWNTREND")
    print("Candle:",
      "GREEN" if latest["close"] > latest["open"] else "RED")
    print("Prev Low:", prev["low"])
    print("Prev High:", prev["high"])


if __name__ == "__main__":
    main()