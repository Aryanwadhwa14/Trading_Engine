# EMA Pullback Strategy - 4 trading strategies

This trading engine implements four EMA-based strategies combining trend-following and institutional scalp signals.

Indicators Used

EMA Fast
EMA Slow

These EMAs define the market trend.

---

Strategy 1 — Uptrend Pullback Long

Condition:

EMA_FAST > EMA_SLOW

Previous candle pulls back to EMA zone.

Current candle closes bullish.

Signal:

LONG

Type:

Trend trade (swing)

---

Strategy 2 — Downtrend Pullback Short

Condition:

EMA_FAST < EMA_SLOW

Previous candle touches EMA zone.

Current candle closes bearish.

Signal:

SHORT

Type:

Trend trade (swing)

---

Strategy 3 — Institutional Short

Condition:

Market in uptrend.

Three consecutive red candles appear.

At least one candle overlaps the EMA zone.

Fourth red candle closes below both EMAs.

Signal:

SHORT

Type:

Scalp trade.

---

Strategy 4 — Institutional Long

Condition:

Market in downtrend.

Three consecutive green candles appear.

At least one candle overlaps the EMA zone.

Fourth green candle closes above EMA slow.

Signal:

LONG

Type:

Scalp trade.

---

Signal Priority

Institutional signals have higher priority than pullback signals.

Order:

1. Institutional Short
2. Institutional Long
3. Pullback Short
4. Pullback Long