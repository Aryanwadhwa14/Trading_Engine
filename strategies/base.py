"""
strategies/base.py
──────────────────
Domain models and interfaces for strategy signals and execution contracts.

Enforces strict causal availability:
- signal_time: The timestamp of the completed bar on which the signal condition was identified.
- available_at: The earliest timestamp at which an order can legally be submitted/filled (e.g. bar t+1 open).
- reference_price: The closing/mark price at signal identification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal
import pandas as pd


@dataclass
class Signal:
    """
    Typed proposal for a trade emitted by a strategy.

    A Signal is a proposal, not an approved order. It cannot execute before `available_at`.
    """
    symbol: str
    side: Literal["LONG", "SHORT"]
    strategy_id: int
    signal_type: Literal["trend", "scalp"]
    signal_time: pd.Timestamp
    available_at: pd.Timestamp
    reference_price: float
    stop_loss: float
    take_profit: float
    timeframe: str
    reason: str
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate side
        if self.side not in ("LONG", "SHORT"):
            raise ValueError(f"Invalid signal side: {self.side}. Must be 'LONG' or 'SHORT'.")

        # Validate prices
        if self.reference_price <= 0:
            raise ValueError(f"reference_price must be positive, got {self.reference_price}")
        if self.stop_loss <= 0:
            raise ValueError(f"stop_loss must be positive, got {self.stop_loss}")
        if self.take_profit <= 0:
            raise ValueError(f"take_profit must be positive, got {self.take_profit}")

        # Validate causal timestamp order: available_at >= signal_time
        if self.available_at < self.signal_time:
            raise ValueError(
                f"available_at ({self.available_at}) cannot precede signal_time ({self.signal_time})"
            )

        # Validate stop loss relative to reference price
        if self.side == "LONG" and self.stop_loss >= self.reference_price:
            raise ValueError(
                f"For LONG, stop_loss ({self.stop_loss}) must be below reference_price ({self.reference_price})"
            )
        if self.side == "SHORT" and self.stop_loss <= self.reference_price:
            raise ValueError(
                f"For SHORT, stop_loss ({self.stop_loss}) must be above reference_price ({self.reference_price})"
            )

    @property
    def entry(self) -> float:
        """Alias for reference_price to maintain backward compatibility."""
        return self.reference_price

    @property
    def signal(self) -> str:
        """Alias for side ('LONG' or 'SHORT') to maintain backward compatibility."""
        return self.side

    @property
    def type(self) -> str:
        """Alias for signal_type to maintain backward compatibility."""
        return self.signal_type

    def __getitem__(self, item: str) -> Any:
        """Dict-like access for backward compatibility with legacy consumers."""
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(f"Signal has no attribute or metadata key '{item}'")

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.metadata

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        """Convert signal to dictionary representation."""
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "side": self.side,
            "signal": self.side,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "type": self.signal_type,
            "signal_type": self.signal_type,
            "signal_time": self.signal_time,
            "available_at": self.available_at,
            "entry": self.reference_price,
            "reference_price": self.reference_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "timeframe": self.timeframe,
            "reason": self.reason,
            "metadata": self.metadata,
        }

