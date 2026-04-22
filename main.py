import time
from config import CONFIG
from data.historical_loader import load_historical_data
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr
from backtest.backtest_engine import run_backtest
from forward_test.forward_test_engine import run_forward_test
from utils.market_schedule import is_market_open

def run_backtest_mode():

    print("\n Running BACKTEST...\n")

    df = load_historical_data(
        ticker=CONFIG["SINGLE_TICKER"],
        interval=CONFIG["TIMEFRAME"],
        start=CONFIG["START_DATE"],
        end=CONFIG["END_DATE"]
    )

    if df is None or df.empty:
        print("❌ No data loaded. Check ticker/timeframe.")
        return

    # Indicators
    df["ema_fast"] = calculate_ema(df, CONFIG["EMA_FAST"])
    df["ema_slow"] = calculate_ema(df, CONFIG["EMA_SLOW"])
    df["atr"] = calculate_atr(df, CONFIG["ATR_PERIOD"])

    run_backtest(
        df,
        CONFIG,
        CONFIG["START_DATE"],
        CONFIG["END_DATE"]
    )


def run_forward_mode():

    print("\n Running FORWARD TEST (LIVE)...\n")
    
    enability = CONFIG.get("TICKER_ENABILITY", "single")
    
    if enability == "multi":
        tickers = CONFIG.get("MULTI_TICKER", [])
    else:
        # Single mode fallback
        ticker_val = CONFIG.get("SINGLE_TICKER", "NVDA")
        tickers = [ticker_val]
        
    print(f"Starting Live Trading Engine for ({enability} mode): {', '.join(tickers)}...\n")
    
    while True:
        try:
            for ticker in tickers:
                if is_market_open(ticker):
                    print(f"[{time.strftime('%H:%M:%S')}] Market is OPEN for {ticker}. Running scanner...")
                    
                    # Create an override config specifically for this ticker iteration
                    ticker_config = CONFIG.copy()
                    ticker_config["SINGLE_TICKER"] = ticker
                    run_forward_test(ticker_config)
                    
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Market is CLOSED for {ticker}. Waiting...")
            
            print(f"\n[{time.strftime('%H:%M:%S')}] Cycle complete. Sleeping for 60 seconds...\n")
            # Sleep for 60 seconds before next full cycle
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n⏹ Live Trading Engine stopped by user.")
            break
        except Exception as e:
            print(f"\n❌ Error in live loop: {e}")
            time.sleep(60)

def main():

    mode = CONFIG.get("MODE", "backtest")

    if mode == "backtest":
        run_backtest_mode()

    elif mode == "forward":
        run_forward_mode()

    else:
        print(" Invalid MODE in config. Use BACKTEST or FORWARD.")


if __name__ == "__main__":
    main()