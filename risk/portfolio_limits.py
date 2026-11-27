"""
risk/portfolio_limits.py
────────────────────────
Portfolio-level risk gates enforcing maximum concurrent positions,
gross exposure caps, per-symbol exposure caps, and daily loss halts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRiskConfig:
    """Configuration for portfolio-level exposure and loss limits."""
    max_open_positions: int = 3
    max_gross_exposure: float = 0.80
    max_symbol_exposure: float = 0.50
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float | None = None


@dataclass(frozen=True)
class PortfolioRiskDecision:
    """Outcome of evaluating a proposed trade against portfolio limits."""
    is_approved: bool
    max_allowed_notional: float
    rejection_reason: str | None = None


def check_portfolio_limits(
    symbol: str,
    current_equity: float,
    day_start_equity: float,
    peak_equity: float,
    open_positions_count: int,
    has_symbol_position: bool,
    current_gross_exposure: float,
    limits: PortfolioRiskConfig,
) -> PortfolioRiskDecision:
    """
    Evaluate whether a new position in `symbol` is permitted under portfolio limits.

    Returns a PortfolioRiskDecision with `max_allowed_notional` capped by remaining
    gross exposure and per-symbol exposure headroom.
    """
    if current_equity <= 0:
        return PortfolioRiskDecision(
            is_approved=False,
            max_allowed_notional=0.0,
            rejection_reason=f"Non-positive portfolio equity: {current_equity:.2f}",
        )

    if has_symbol_position:
        return PortfolioRiskDecision(
            is_approved=False,
            max_allowed_notional=0.0,
            rejection_reason=f"Position already open for {symbol}",
        )

    # 1. Daily loss halt
    if day_start_equity > 0 and limits.max_daily_loss_pct > 0:
        daily_loss_frac = (day_start_equity - current_equity) / day_start_equity
        if daily_loss_frac >= limits.max_daily_loss_pct:
            return PortfolioRiskDecision(
                is_approved=False,
                max_allowed_notional=0.0,
                rejection_reason=(
                    f"Daily loss halt triggered: {daily_loss_frac * 100:.2f}% >= "
                    f"{limits.max_daily_loss_pct * 100:.2f}%"
                ),
            )

    # 2. Max drawdown halt (optional)
    if limits.max_drawdown_pct is not None and peak_equity > 0:
        dd_frac = (peak_equity - current_equity) / peak_equity
        if dd_frac >= limits.max_drawdown_pct:
            return PortfolioRiskDecision(
                is_approved=False,
                max_allowed_notional=0.0,
                rejection_reason=(
                    f"Max drawdown halt triggered: {dd_frac * 100:.2f}% >= "
                    f"{limits.max_drawdown_pct * 100:.2f}%"
                ),
            )

    # 3. Max concurrent open positions
    if open_positions_count >= limits.max_open_positions:
        return PortfolioRiskDecision(
            is_approved=False,
            max_allowed_notional=0.0,
            rejection_reason=(
                f"Max open positions reached: {open_positions_count} >= {limits.max_open_positions}"
            ),
        )

    # 4. Exposure headroom (gross & per-symbol)
    max_gross_dollars = current_equity * limits.max_gross_exposure
    remaining_gross = max(0.0, max_gross_dollars - current_gross_exposure)
    max_symbol_dollars = current_equity * limits.max_symbol_exposure
    max_allowed_notional = min(remaining_gross, max_symbol_dollars)

    if max_allowed_notional <= 0.0:
        return PortfolioRiskDecision(
            is_approved=False,
            max_allowed_notional=0.0,
            rejection_reason=(
                f"Gross exposure limit reached: ${current_gross_exposure:.2f} / "
                f"${max_gross_dollars:.2f}"
            ),
        )

    return PortfolioRiskDecision(
        is_approved=True,
        max_allowed_notional=max_allowed_notional,
        rejection_reason=None,
    )

