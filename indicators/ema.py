def calculate_ema(df, period, column="close"):

    ema = df[column].ewm(
        span=period,
        adjust=False
    ).mean()

    return ema