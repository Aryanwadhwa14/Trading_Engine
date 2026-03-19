import yfinance as yf
import pandas as pd


def load_live_data(ticker: str, interval: str = "5m") -> pd.DataFrame:
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

    raw = yf.download(
        tickers=ticker,
        period="5d",
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