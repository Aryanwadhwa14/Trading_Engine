import yfinance as yf
import pandas as pd
import datetime as dt
from data.validation import validate_ohlcv

def load_live_data(ticker: str, interval: str = "5m", max_ema_length: int = 200) -> pd.DataFrame:
    """
    Download live OHLCV data from yfinance and return a clean DataFrame.

    Handles:
    - Multi-index columns (yfinance >= 0.2.x returns ("Close", "TICKER") tuples)
    - Mixed-case column names
    - Unexpected extra columns
    - NaN rows

    Returns a DataFrame with columns: [open, high, low, close, volume]
    Index: DatetimeIndex (UTC or local, depending on yfinance version)
    """

    # ── Dynamic Concept: Context-Based Burn-In Calculation ──────────────────
    # Instead of manual "period" strings (like "1mo"), we calculate exactly 
    # the amount of history required by the configuration (e.g. 4x the max EMA).

    minutes_per_candle = 5
    if interval.endswith('m'):
        minutes_per_candle = int(interval[:-1])
    elif interval.endswith('h'):
        minutes_per_candle = int(interval[:-1]) * 60
    elif interval.endswith('d'):
        minutes_per_candle = int(interval[:-1]) * 1440

    # Estimate candles per 6.5h trading day (US normal hours)
    candles_per_day = max(1, 390 / minutes_per_candle)
    target_candles = max(max_ema_length * 4, 100)
    
    # Required calendar days (added 45% buffer for weekends and holidays)
    days_needed = int((target_candles / candles_per_day) * 1.45)
    days_needed = max(days_needed, 5)

    # Secure against yfinance intraday historical limits
    if minutes_per_candle == 1:
        days_needed = min(days_needed, 7)
    elif minutes_per_candle < 60:
        days_needed = min(days_needed, 59)
    elif minutes_per_candle < 1440:
        days_needed = min(days_needed, 720)
    # else: daily and above have no tight historical limits.

    start_time = dt.datetime.now() - dt.timedelta(days=days_needed)

    raw = yf.download(
        tickers=ticker,
        start=start_time.strftime('%Y-%m-%d'),
        interval=interval,
        progress=False,
        auto_adjust=True,   # avoids Adj Close confusion
    )

    if raw.empty:
        raise ValueError(f"[live_data_loader] No data returned for {ticker} / {interval}")

    df = raw.copy()

    # ── Fix multi-index columns ────────────────────────────────────────────────
    # yfinance >= 0.2.x: columns are MultiIndex like ("Close", "QQQ")
    # We drop the ticker level so we get plain string column names.
    if isinstance(df.columns, pd.MultiIndex):
        # Level 0 = price field, Level 1 = ticker symbol
        df.columns = [col[0] for col in df.columns]

    # ── Normalise column names to lowercase ───────────────────────────────────
    df.columns = [str(c).strip().lower() for c in df.columns]

    # ── Keep only the five OHLCV columns we need ──────────────────────────────
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"[live_data_loader] Missing columns after normalisation: {missing}. "
            f"Available: {list(df.columns)}"
        )

    df = df[required]

    # ── Drop rows with any NaN in OHLCV ───────────────────────────────────────
    df.dropna(subset=required, inplace=True)

    # ── Ensure numeric dtype (guards against object columns) ──────────────────
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(subset=required, inplace=True)

    if df.empty:
        raise ValueError(
            f"[live_data_loader] DataFrame is empty after cleaning for {ticker} / {interval}"
        )

    validated_df, _ = validate_ohlcv(df, raise_on_error=True, timeframe=interval)
    return validated_df