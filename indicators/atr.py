import numpy as np


def calculate_atr(df, period=14):

    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1))
        )
    )

    atr = tr.rolling(period).mean()

    return atr