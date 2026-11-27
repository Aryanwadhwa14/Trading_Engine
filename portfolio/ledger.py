"""
portfolio/ledger.py
───────────────────
Single source of truth for cash, multi-asset open positions, realized/unrealized P&L,
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
    Maintains authoritative cash, multi-asset positions, and P&L accounting.

    Accounting Invariants:
    - net_pnl = gross_pnl - slippage_cost - commission_cost
    - When flat: cash == initial_balance + realized_pnl
    - equity = cash + sum(signed_marked_position_values)
    """

    def __init__(self, initial_balance: float) -> None:
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        self.initial_balance = float(initial_balance)
        self.cash = float(initial_balance)
        self.realized_pnl = 0.0
        self.total_commissions = 0.0
        self.total_slippage = 0.0
        self.positions: dict[str, Position] = {}

    @property
    def is_flat(self) -> bool:
        return len(self.positions) == 0

    @property
    def open_position_count(self) -> int:
        return len(self.positions)

    @property
    def position(self) -> Position | None:
        """Backward-compatible accessor for single-asset mode."""
        if not self.positions:
            return None
        if len(self.positions) == 1:
            return next(iter(self.positions.values()))
        raise RuntimeError(
            "Multiple positions open; access ledger.positions[symbol] instead of ledger.position."
        )

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def gross_exposure(self, mark_prices: dict[str, float] | None = None) -> float:
        """Compute total absolute marked notional across all open positions."""
        total = 0.0
        for sym, pos in self.positions.items():
            px = mark_prices.get(sym, pos.entry_price) if mark_prices else pos.entry_price
            total += abs(pos.quantity * px)
        return total

    def mark_to_market_equity(
        self, mark_prices: float | dict[str, float] | None = None
    ) -> float:
        """
        Compute current portfolio equity: cash + sum(signed marked position values).
        Accepts either a float (single-asset mode) or a dict {symbol: mark_price}.
        """
        if not self.positions:
            return self.cash

        equity = self.cash
        for sym, pos in self.positions.items():
            if isinstance(mark_prices, dict):
                px = mark_prices.get(sym, pos.entry_price)
            elif isinstance(mark_prices, (int, float)):
                px = float(mark_prices)
            else:
                px = pos.entry_price

            if pos.side == "LONG":
                equity += pos.quantity * px
            else:
                equity -= pos.quantity * px
        return equity

    def unrealized_pnl(self, mark_prices: float | dict[str, float]) -> float:
        """Compute total unrealized P&L across all open positions (excluding exit costs)."""
        if not self.positions:
            return 0.0

        total = 0.0
        for sym, pos in self.positions.items():
            px = mark_prices.get(sym, pos.entry_price) if isinstance(mark_prices, dict) else float(mark_prices)
            if pos.side == "LONG":
                total += (px - pos.entry_price) * pos.quantity
            else:
                total += (pos.entry_price - px) * pos.quantity
        return total

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
        """Record an entry fill for `symbol` and update shared cash."""
        if symbol in self.positions:
            raise RuntimeError(f"Position already open for {symbol}.")
        if entry_fill.action != "ENTRY":
            raise ValueError("open_position requires an ENTRY FillResult.")

        notional = entry_fill.fill_price * entry_fill.quantity
        if entry_fill.side == "LONG":
            self.cash -= (notional + entry_fill.commission)
        else:
            self.cash += (notional - entry_fill.commission)

        self.total_commissions += entry_fill.commission
        self.total_slippage += entry_fill.slippage_cost

        pos = Position(
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
        self.positions[symbol] = pos
        return pos

    def close_position(self, exit_fill: FillResult, symbol: str | None = None) -> ClosedTrade:
        """Record an exit fill for `symbol`, settle shared cash, and compute gross & net P&L."""
        if not self.positions:
            raise RuntimeError("Cannot close position when portfolio is flat.")

        if symbol is None:
            if len(self.positions) == 1:
                symbol = next(iter(self.positions.keys()))
            else:
                raise ValueError("`symbol` must be specified when multiple positions are open.")

        if symbol not in self.positions:
            raise KeyError(f"No open position found for symbol '{symbol}'.")

        pos = self.positions.pop(symbol)
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
