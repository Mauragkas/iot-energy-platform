"""Meter sliding window encapsulating ring buffer and rolling stats."""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models import TelemetryReading


class MeterSlidingWindow:
    """Encapsulates per-meter bounded ring buffer and rolling statistics (mean, std, EWMA).

    Single Responsibility: Maintains rolling telemetry state for a single smart meter.
    """

    def __init__(self, capacity: int = 60, alpha: float = 0.2) -> None:
        if capacity < 1:
            raise ValueError("Window capacity must be at least 1")
        if not (0.0 < alpha <= 1.0):
            raise ValueError("EWMA alpha must be in range (0.0, 1.0]")

        self.capacity: int = capacity
        self.alpha: float = alpha
        self._buffer: deque[TelemetryReading] = deque(maxlen=capacity)
        self._ewma: Optional[float] = None

    def add(self, reading: TelemetryReading) -> None:
        """Append a reading to the sliding window and update EWMA."""
        self._buffer.append(reading)
        value = reading.active_power_kw
        if self._ewma is None:
            self._ewma = value
        else:
            self._ewma = self.alpha * value + (1.0 - self.alpha) * self._ewma

    def reset(self) -> None:
        """Clear the window and reset EWMA state (e.g. on partition rebalance)."""
        self._buffer.clear()
        self._ewma = None

    @property
    def count(self) -> int:
        """Number of readings currently buffered in the window."""
        return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        """Whether the window is empty."""
        return len(self._buffer) == 0

    @property
    def is_full(self) -> bool:
        """Whether the window has reached maximum capacity."""
        return len(self._buffer) >= self.capacity

    @property
    def latest(self) -> Optional[TelemetryReading]:
        """Most recent reading in the window, or None if empty."""
        return self._buffer[-1] if self._buffer else None

    @property
    def readings(self) -> list[TelemetryReading]:
        """Copy of buffered readings in chronological order."""
        return list(self._buffer)

    @property
    def mean(self) -> float:
        """Rolling arithmetic mean of active_power_kw in the window."""
        if not self._buffer:
            return 0.0
        return sum(r.active_power_kw for r in self._buffer) / len(self._buffer)

    @property
    def std(self) -> float:
        """Rolling sample standard deviation (N-1 Bessel's correction) of active_power_kw."""
        n = len(self._buffer)
        if n < 2:
            return 0.0
        avg = self.mean
        variance = sum((r.active_power_kw - avg) ** 2 for r in self._buffer) / (n - 1)
        return math.sqrt(variance)

    @property
    def ewma(self) -> float:
        """Exponentially weighted moving average of active_power_kw."""
        return self._ewma if self._ewma is not None else 0.0
