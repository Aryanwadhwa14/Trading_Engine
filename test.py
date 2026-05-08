import yfinance as yf
import os

def download_historical_data(ticker: str, period: str = "1mo", interval: str = "5m"):
    """
    Downloads historical data from yfinance and saves it to a CSV file.
    """
    output_dir = os.path.join("data", "historical_csvs")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        print(f"Downloading data for {ticker} (Period: {period}, Interval: {interval})...")
        df = yf.download(tickers=ticker, period=period, interval=interval, progress=False)
        
        if df is not None and not df.empty:
            # yfinance index usually has a timezone (America/New_York)
            # If not, we localize to America/New_York first, then convert to PST
            if df.index.tz is None:
                df.index = df.index.tz_localize('America/New_York').tz_convert('US/Pacific')
            else:
                df.index = df.index.tz_convert('US/Pacific')
                
            filename = f"{ticker}_{period}_{interval}.csv"
            filepath = os.path.join(output_dir, filename)
            df.to_csv(filepath)
            print(f"Successfully saved {len(df)} rows to {filepath}")
        else:
            print(f"No data found for {ticker} with period {period} and interval {interval}.")
    except Exception as e:
        print(f"Error downloading data: {e}")

if __name__ == "__main__":
    download_historical_data("NVDA", period="1mo", interval="5m")