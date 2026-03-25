import yfinance as yf
import pandas as pd


def _calculate_yf_period(interval: str, max_ema_length: int) -> str:
    """
    Calculate the exact yfinance period string needed to get enough 
    candles for indicator burn-in (approx 4x the longest EMA).
    """
    target_candles = max(max_ema_length * 4, 100) # At least 100 candles

    # Approximate candles per 6.5h trading day (US normal hours)
    # Crypto will return more candles per day, so this is the conservative estimate.
    candles_per_day = {
        "1m": 390,
        "2m": 195,
        "5m": 78,
        "15m": 26,
        "30m": 13,
        "60m": 7,
        "1h": 7,
        "90m": 4,
        "1d": 1,
    }
    
    cpd = candles_per_day.get(interval, 78) # Default to 5m assumption
    days_needed = target_candles / cpd
    
    # yfinance max limits for intraday:
    # 1m = max 7 days
    # 2m, 5m, 15m, 30m, 90m = max 60 days
    # 1h, 60m = max 730 days
    
    # Clamp days to valid yfinance strings
    if interval == "1m":
        return "7d" # Max allowed
        
    if interval in ["2m", "5m", "15m", "30m", "90m"]:
        if days_needed <= 5: return "5d"
        if days_needed <= 20: return "1mo"
        return "60d" # Max allowed
        
    if interval in ["60m", "1h"]:
        if days_needed <= 5: return "5d"
        if days_needed <= 20: return "1mo"
        if days_needed <= 60: return "3mo"
        if days_needed <= 125: return "6mo"
        if days_needed <= 250: return "1y"
        return "2y" # Max allowed

    # Daily or higher
    if days_needed <= 250: return "1y"
    if days_needed <= 500: return "2y"
    if days_needed <= 1250: return "5y"
    if days_needed <= 2500: return "10y"
    return "max"


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

    period = _calculate_yf_period(interval, max_ema_length)

    raw = yf.download(
        tickers=ticker,
        period=period,
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

    return df