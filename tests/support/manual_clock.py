"""Re-export the deterministic clock for test ergonomics."""

from server import ManualClock

__all__ = ["ManualClock"]
