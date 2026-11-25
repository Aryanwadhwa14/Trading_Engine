"""
portfolio/ledger.py
───────────────────
Single source of truth for cash, open positions, realized/unrealized P&L,
commissions, slippage, and mark-to-market equity reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from execution.fill_simulator import FillResult


@dataclass
class Position:
    """Represents an active open position in the portfolio."""
    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: int
    entry_price: float
    nominal_entry_price: float
    entry_commission: float
    entry_slippage: float
    stop_loss: float
    take_profit: float
    entry_time: Any
    signal_time: Any
    entry_reason: str
    trade_type: str
    strategy_id: int
    risk_budget: float
    estimated_risk: float


@dataclass(frozen=True)
class ClosedTrade:
    """Immutable record of a completed round-trip trade with full cost attribution."""
    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: int
    entry_price: float
    exit_price: float
    nominal_entry_price: float
    nominal_exit_price: float
    gross_pnl: float
    slippage_cost: float
    commission_cost: float
    net_pnl: float
    exit_reason: str
    ambiguous_bar: bool


class PortfolioLedger:
    """
    Maintains authoritative cash, position, and P&L accounting.

    Accounting Invariants:
    - net_pnl = gross_pnl - slippage_cost - commission_cost
    - When flat: cash == initial_balance + realized_pnl
    - equity = cash + marked_position_value
    """

    def __init__(self, initial_balance: float) -> None:
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        self.initial_balance = float(initial_balance)
        self.cash = float(initial_balance)
        self.realized_pnl = 0.0
        self.total_commissions = 0.0
        self.total_slippage = 0.0
        self.position: Position | None = None

    @property
    def is_flat(self) -> bool:
        return self.position is None

    def mark_to_market_equity(self, mark_price: float | None = None) -> float:
        """Compute current equity: cash + marked position value."""
        if self.position is None:
            return self.cash
        if mark_price is None:
            mark_price = self.position.entry_price
        if self.position.side == "LONG":
            return self.cash + (self.position.quantity * mark_price)
        # SHORT: cash includes initial short sale proceeds, subtract buy-back liability
        return self.cash - (self.position.quantity * mark_price)

    def unrealized_pnl(self, mark_price: float) -> float:
        """Compute current unrealized P&L at `mark_price` (excluding exit costs)."""
        if self.position is None:
            return 0.0
        if self.position.side == "LONG":
            return (mark_price - self.position.entry_price) * self.position.quantity
        return (self.position.entry_price - mark_price) * self.position.quantity

    def open_position(
        self,
        symbol: str,
        entry_fill: FillResult,
        stop_loss: float,
        take_profit: float,
        entry_time: Any,
        signal_time: Any,
        entry_reason: str,
        trade_type: str,
        strategy_id: int,
        risk_budget: float,
        estimated_risk: float,
    ) -> Position:
        """Record an entry fill and update cash."""
        if self.position is not None:
            raise RuntimeError("Cannot open position while another position is active.")
        if entry_fill.action != "ENTRY":
            raise ValueError("open_position requires an ENTRY FillResult.")

        notional = entry_fill.fill_price * entry_fill.quantity
        if entry_fill.side == "LONG":
            self.cash -= (notional + entry_fill.commission)
        else:
            self.cash += (notional - entry_fill.commission)

        self.total_commissions += entry_fill.commission
        self.total_slippage += entry_fill.slippage_cost

        self.position = Position(
            symbol=symbol,
            side=entry_fill.side,
            quantity=entry_fill.quantity,
            entry_price=entry_fill.fill_price,
            nominal_entry_price=entry_fill.nominal_price,
            entry_commission=entry_fill.commission,
            entry_slippage=entry_fill.slippage_cost,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=entry_time,
            signal_time=signal_time,
            entry_reason=entry_reason,
            trade_type=trade_type,
            strategy_id=strategy_id,
            risk_budget=risk_budget,
            estimated_risk=estimated_risk,
        )
        return self.position

    def close_position(self, exit_fill: FillResult) -> ClosedTrade:
        """Record an exit fill, settle cash, and compute gross & net P&L."""
        if self.position is None:
            raise RuntimeError("Cannot close position when portfolio is flat.")
        if exit_fill.action != "EXIT":
            raise ValueError("close_position requires an EXIT FillResult.")

        pos = self.position
        qty = pos.quantity
        exit_notional = exit_fill.fill_price * qty

        if pos.side == "LONG":
            self.cash += (exit_notional - exit_fill.commission)
            gross_pnl = (exit_fill.nominal_price - pos.nominal_entry_price) * qty
        else:
            self.cash -= (exit_notional + exit_fill.commission)
            gross_pnl = (pos.nominal_entry_price - exit_fill.nominal_price) * qty

        total_slippage = pos.entry_slippage + exit_fill.slippage_cost
        total_commissions = pos.entry_commission + exit_fill.commission
        net_pnl = gross_pnl - total_slippage - total_commissions

        self.total_commissions += exit_fill.commission
        self.total_slippage += exit_fill.slippage_cost
        self.realized_pnl += net_pnl
        self.position = None

        return ClosedTrade(
            symbol=pos.symbol,
            side=pos.side,
            quantity=qty,
            entry_price=pos.entry_price,
            exit_price=exit_fill.fill_price,
            nominal_entry_price=pos.nominal_entry_price,
            nominal_exit_price=exit_fill.nominal_price,
            gross_pnl=gross_pnl,
            slippage_cost=total_slippage,
            commission_cost=total_commissions,
            net_pnl=net_pnl,
            exit_reason=exit_fill.exit_reason or "Exit",
            ambiguous_bar=exit_fill.ambiguous_bar,
        )

