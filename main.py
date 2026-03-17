from config import CONFIG
from data.historical_loader import load_historical_data
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr
from backtest.backtest_engine import run_backtest


def main():

    df = load_historical_data(
        ticker=CONFIG["TICKER"],
        interval=CONFIG["TIMEFRAME"]
    )

    df["ema_fast"] = calculate_ema(df, CONFIG["EMA_FAST"])
    df["ema_slow"] = calculate_ema(df, CONFIG["EMA_SLOW"])
    df["atr"] = calculate_atr(df, CONFIG["ATR_PERIOD"])

    run_backtest(df, CONFIG)


if __name__ == "__main__":
    main()