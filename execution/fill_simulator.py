"""
execution/fill_simulator.py
───────────────────────────
Deterministic bar-based fill simulator with configurable commissions,
adverse slippage, gap handling, and conservative stop-first conflict resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FillResult:
    """Immutable record of a simulated order execution."""
    fill_price: float
    nominal_price: float
    quantity: int
    side: Literal["LONG", "SHORT"]
    action: Literal["ENTRY", "EXIT"]
    exit_reason: str | None
    commission: float
    slippage_cost: float
    ambiguous_bar: bool = False


def _apply_adverse_slippage(
    nominal_price: float,
    trade_direction: Literal["BUY", "SELL"],
    slippage_bps: float,
) -> float:
    """Apply adverse slippage: buys pay more, sells receive less."""
    if slippage_bps <= 0.0:
        return nominal_price
    slip_frac = slippage_bps / 10_000.0
    if trade_direction == "BUY":
        return nominal_price * (1.0 + slip_frac)
    return nominal_price * (1.0 - slip_frac)


def simulate_entry_fill(
    reference_open: float,
    quantity: int,
    side: Literal["LONG", "SHORT"],
    commission_rate: float = 0.0,
    slippage_bps: float = 0.0,
) -> FillResult:
    """
    Simulate an entry fill at bar open with adverse slippage and commission.
    """
    direction: Literal["BUY", "SELL"] = "BUY" if side == "LONG" else "SELL"
    fill_price = _apply_adverse_slippage(reference_open, direction, slippage_bps)
    notional = fill_price * quantity
    commission = notional * commission_rate
    slippage_cost = abs(fill_price - reference_open) * quantity

    return FillResult(
        fill_price=fill_price,
        nominal_price=reference_open,
        quantity=quantity,
        side=side,
        action="ENTRY",
        exit_reason=None,
        commission=commission,
        slippage_cost=slippage_cost,
        ambiguous_bar=False,
    )


def simulate_exit_fill(
    bar_open: float,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    quantity: int,
    side: Literal["LONG", "SHORT"],
    stop_loss: float,
    take_profit: float,
    is_last_candle: bool,
    commission_rate: float = 0.0,
    slippage_bps: float = 0.0,
    stop_target_conflict: str = "stop_first",
    close_at_end: bool = True,
) -> FillResult | None:
    """
    Evaluate whether an open position exits on the current OHLC bar.

    Rules:
    1. Gap-through-stop at bar open fills conservatively at `bar_open` + adverse slippage.
    2. Gap-through-target at bar open fills at `bar_open` (no adverse slippage on favorable gap).
    3. Intrabar both SL and TP crossed: uses `stop_target_conflict` ('stop_first' default)
       and flags `ambiguous_bar = True`.
    4. Stop-loss and EOD Close incur adverse slippage; limit Take-Profit does not.
    """
    nominal_price: float | None = None
    exit_reason: str | None = None
    apply_slippage = False
    ambiguous_bar = False

    if side == "LONG":
        # 1. Check opening gaps first
        if bar_open <= stop_loss:
            nominal_price = bar_open
            exit_reason = "Gap SL"
            apply_slippage = True
        elif bar_open >= take_profit:
            nominal_price = bar_open
            exit_reason = "Gap TP"
            apply_slippage = False
        else:
            # 2. Check intrabar hits
            hit_sl = bar_low <= stop_loss
            hit_tp = bar_high >= take_profit
            ambiguous_bar = hit_sl and hit_tp

            if hit_sl and (not hit_tp or stop_target_conflict == "stop_first"):
                nominal_price = stop_loss
                exit_reason = "SL Hit"
                apply_slippage = True
            elif hit_tp:
                nominal_price = take_profit
                exit_reason = "TP Hit"
                apply_slippage = False
            elif is_last_candle and close_at_end:
                nominal_price = bar_close
                exit_reason = "EOD Close"
                apply_slippage = True

        exit_direction: Literal["BUY", "SELL"] = "SELL"

    else:  # SHORT
        # 1. Check opening gaps first
        if bar_open >= stop_loss:
            nominal_price = bar_open
            exit_reason = "Gap SL"
            apply_slippage = True
        elif bar_open <= take_profit:
            nominal_price = bar_open
            exit_reason = "Gap TP"
            apply_slippage = False
        else:
            # 2. Check intrabar hits
            hit_sl = bar_high >= stop_loss
            hit_tp = bar_low <= take_profit
            ambiguous_bar = hit_sl and hit_tp

            if hit_sl and (not hit_tp or stop_target_conflict == "stop_first"):
                nominal_price = stop_loss
                exit_reason = "SL Hit"
                apply_slippage = True
            elif hit_tp:
                nominal_price = take_profit
                exit_reason = "TP Hit"
                apply_slippage = False
            elif is_last_candle and close_at_end:
                nominal_price = bar_close
                exit_reason = "EOD Close"
                apply_slippage = True

        exit_direction = "BUY"

    if nominal_price is None or exit_reason is None:
        return None

    fill_price = (
        _apply_adverse_slippage(nominal_price, exit_direction, slippage_bps)
        if apply_slippage
        else nominal_price
    )
    notional = fill_price * quantity
    commission = notional * commission_rate
    slippage_cost = abs(fill_price - nominal_price) * quantity

    return FillResult(
        fill_price=fill_price,
        nominal_price=nominal_price,
        quantity=quantity,
        side=side,
        action="EXIT",
        exit_reason=exit_reason,
        commission=commission,
        slippage_cost=slippage_cost,
        ambiguous_bar=ambiguous_bar,
    )

