import yfinance as yf

for interval in ["1m", "5m", "15m", "1h"]:
    try:
        df = yf.download(tickers="AAPL", period="max", interval=interval, progress=False)
        if df is not None:
            print(f"{interval}: {len(df)} rows")
    except Exception as e:
        print(f"{interval}: Error {e}")