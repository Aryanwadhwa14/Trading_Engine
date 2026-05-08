import os
import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from polygon import RESTClient
import sys

# Ensure we can import config from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

# Load environment variables
load_dotenv()
api_key = os.getenv("POLYGON_API_KEY")
if not api_key:
    raise ValueError("POLYGON_API_KEY not found in .env file. Please add it.")

# Initialize the Polygon client
client = RESTClient(api_key)

def parse_timeframe(tf_str):
    """Convert '5m' to (5, 'minute') for Polygon API"""
    if tf_str.endswith('m'):
        return int(tf_str[:-1]), 'minute'
    elif tf_str.endswith('h'):
        return int(tf_str[:-1]), 'hour'
    elif tf_str.endswith('d'):
        return int(tf_str[:-1]), 'day'
    else:
        return 1, 'day'

def download_for_ticker(ticker, start, end, multiplier, timespan):
    print(f"Fetching Polygon data for {ticker} from {start} to {end} ({multiplier} {timespan})...")
    
    aggs = []
    try:
        # list_aggs handles pagination under the hood if it exceeds 50000
        for a in client.list_aggs(
            ticker,
            multiplier,
            timespan,
            start,
            end,
            limit=50000,
        ):
            aggs.append(a)
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return
        
    if not aggs:
        print(f"No data found for {ticker}. (Is it a weekend/holiday?)")
        return

    df = pd.DataFrame(aggs)
    
    # Polygon returns timestamp in milliseconds as 'timestamp'
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    
    # Convert from UTC to PST (US/Pacific)
    df.index = df.index.tz_localize('UTC').tz_convert('US/Pacific')
    
    # Filter to keep only Regular Trading Hours (9:30 AM - 4:00 PM ET -> 6:30 AM - 1:00 PM PST)
    df = df.between_time('06:30', '13:00')
    
    # Keep only OHLCV
    # Polygon natively returns 'open', 'high', 'low', 'close', 'volume'
    if all(c in df.columns for c in ['open', 'high', 'low', 'close', 'volume']):
        df = df[['open', 'high', 'low', 'close', 'volume']]
    else:
        print(f"Unexpected columns from Polygon: {df.columns}")
        return
    
    # Save it locally
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historical_csvs")
    os.makedirs(save_dir, exist_ok=True)
    
    # Name format: AAPL_5m_2023-01-01_to_2023-12-31.csv
    filename = os.path.join(save_dir, f"{ticker}_{CONFIG['TIMEFRAME']}_{start}_to_{end}.csv")
    df.to_csv(filename)
    print(f"✅ Saved {len(df)} rows to {filename}")

def main():
    use_multi = CONFIG["USE_MULTI"]
    tickers = CONFIG["MULTI_TICKER"] if use_multi else [CONFIG["SINGLE_TICKER"]]
    
    start = CONFIG["START_DATE"]
    end = CONFIG["END_DATE"]
    multiplier, timespan = parse_timeframe(CONFIG["TIMEFRAME"])

    print(f"--- Starting Polygon.io Downloader ---")
    for i, ticker in enumerate(tickers):
        download_for_ticker(ticker, start, end, multiplier, timespan)
        
        # Free tier is 5 calls per minute. Sleep 12.5 seconds between calls to be safe.
        if i < len(tickers) - 1:
            print("⏳ Waiting 13 seconds to respect Polygon free tier rate limits...")
            time.sleep(13)
            
    print("\n🎉 All downloads complete!")

if __name__ == "__main__":
    main()
