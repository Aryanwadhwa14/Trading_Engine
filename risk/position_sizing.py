"""
risk/position_sizing.py
───────────────────────
Pure, deterministic risk-based position sizing module for cash equities.

Rules & Invariants:
1. risk_budget = equity * risk_percent
2. risk_per_unit = abs(entry_price - stop_price) * point_value
3. quantity_by_risk = floor(risk_budget / risk_per_unit)
4. quantity_by_cash = floor(cash_available / (entry_price * point_value))
5. quantity = min(quantity_by_risk, quantity_by_cash, max_position_units or infinity)
6. Fail-closed: invalid stops, non-positive prices, negative equity, or invalid risk fractions
   return quantity = 0 with a descriptive rejection reason.
7. Never force quantity to at least 1 unit if capital or risk budget is insufficient.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PositionSizingResult:
    """Immutable result of a position sizing calculation."""
    quantity: int
    is_approved: bool
    risk_budget: float
    risk_per_unit: float
    cash_required: float
    estimated_risk: float
    rejection_reason: str | None = None


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_price: float,
    risk_percent: float,
    cash_available: float | None = None,
    side: Literal["LONG", "SHORT"] = "LONG",
    point_value: float = 1.0,
    max_position_units: int | None = None,
) -> PositionSizingResult:
    """
    Calculate deterministic, risk-managed position size for cash equities.

    Parameters
    ----------
    equity : float
        Current total portfolio equity (cash + unrealized value). Must be > 0.
    entry_price : float
        Planned execution price. Must be > 0.
    stop_price : float
        Planned protective stop price. Must be > 0.
    risk_percent : float
        Fraction of equity risked per trade (e.g. 0.01 for 1%). Must be in (0, 1].
    cash_available : float, optional
        Current available cash / buying power. If None, defaults to `equity`. Must be >= 0.
    side : {"LONG", "SHORT"}
        Trade direction.
        For LONG: stop_price must be < entry_price.
        For SHORT: stop_price must be > entry_price.
    point_value : float, default 1.0
        Contract/point multiplier (1.0 for standard US equities). Must be > 0.
    max_position_units : int, optional
        Optional hard cap on allowable unit count.

    Returns
    -------
    PositionSizingResult
        Typed outcome with quantity (>= 0), approval flag, and financial details.
    """
    if cash_available is None:
        cash_available = equity

    # ── 1. Validate Equity & Cash ──────────────────────────────────────────
    if equity <= 0:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Non-positive equity: {equity:.2f}",
        )

    if cash_available <= 0:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Insufficient available cash: {cash_available:.2f}",
        )

    # ── 2. Validate Risk Fraction ──────────────────────────────────────────
    if not (0.0 < risk_percent <= 1.0):
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Invalid risk_percent: {risk_percent}. Must be in (0, 1.0].",
        )

    # ── 3. Validate Prices & Multipliers ───────────────────────────────────
    if entry_price <= 0:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Non-positive entry_price: {entry_price:.4f}",
        )

    if stop_price <= 0:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Non-positive stop_price: {stop_price:.4f}",
        )

    if point_value <= 0:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Non-positive point_value: {point_value}",
        )

    # ── 4. Validate Stop Direction and Distance ────────────────────────────
    side_upper = side.upper()
    if side_upper == "LONG":
        if stop_price >= entry_price:
            return PositionSizingResult(
                quantity=0,
                is_approved=False,
                risk_budget=0.0,
                risk_per_unit=0.0,
                cash_required=0.0,
                estimated_risk=0.0,
                rejection_reason=(
                    f"Invalid stop for LONG: stop_price ({stop_price:.4f}) >= "
                    f"entry_price ({entry_price:.4f})"
                ),
            )
    elif side_upper == "SHORT":
        if stop_price <= entry_price:
            return PositionSizingResult(
                quantity=0,
                is_approved=False,
                risk_budget=0.0,
                risk_per_unit=0.0,
                cash_required=0.0,
                estimated_risk=0.0,
                rejection_reason=(
                    f"Invalid stop for SHORT: stop_price ({stop_price:.4f}) <= "
                    f"entry_price ({entry_price:.4f})"
                ),
            )
    else:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=f"Unknown trade side: '{side}'. Must be LONG or SHORT.",
        )

    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 1e-8:
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=0.0,
            risk_per_unit=0.0,
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason="Stop distance is zero or negligible.",
        )

    # ── 5. Mathematical Sizing ─────────────────────────────────────────────
    risk_budget = equity * risk_percent
    risk_per_unit = stop_distance * point_value
    cash_required_per_unit = entry_price * point_value

    qty_by_risk = math.floor(risk_budget / risk_per_unit)
    qty_by_cash = math.floor(cash_available / cash_required_per_unit)

    final_quantity = min(qty_by_risk, qty_by_cash)

    if max_position_units is not None and max_position_units > 0:
        final_quantity = min(final_quantity, max_position_units)

    # ── 6. Final Approval Check (Never force 1 unit) ────────────────────────
    if final_quantity <= 0:
        reason = (
            f"Calculated quantity is 0 (qty_by_risk={qty_by_risk}, "
            f"qty_by_cash={qty_by_cash}, risk_budget=${risk_budget:.2f}, "
            f"risk_per_unit=${risk_per_unit:.2f}, cash_avail=${cash_available:.2f})"
        )
        return PositionSizingResult(
            quantity=0,
            is_approved=False,
            risk_budget=round(risk_budget, 4),
            risk_per_unit=round(risk_per_unit, 4),
            cash_required=0.0,
            estimated_risk=0.0,
            rejection_reason=reason,
        )

    cash_required = final_quantity * cash_required_per_unit
    estimated_risk = final_quantity * risk_per_unit

    return PositionSizingResult(
        quantity=final_quantity,
        is_approved=True,
        risk_budget=round(risk_budget, 4),
        risk_per_unit=round(risk_per_unit, 4),
        cash_required=round(cash_required, 4),
        estimated_risk=round(estimated_risk, 4),
        rejection_reason=None,
    )

