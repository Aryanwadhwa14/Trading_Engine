import numpy as np
import pandas as pd


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) using standard True Range definition:
    TR = max(high - low, abs(high - prev_close), abs(low - prev_close)).
    For the first bar where prev_close is unavailable, TR = high - low.
    """
    hl = df["high"] - df["low"]
    h_prev_c = abs(df["high"] - df["close"].shift(1))
    l_prev_c = abs(df["low"] - df["close"].shift(1))

    # For the first row, shifted close is NaN; fill with high - low
    tr = np.maximum(hl, np.maximum(h_prev_c.fillna(hl), l_prev_c.fillna(hl)))

    atr = tr.rolling(period).mean()

    return atr  

