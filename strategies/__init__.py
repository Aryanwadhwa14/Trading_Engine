"""Strategies package."""
from strategies.base import Signal
from strategies.ema_pullback import generate_signal

__all__ = ["Signal", "generate_signal"]

