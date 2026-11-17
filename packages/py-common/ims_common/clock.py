"""Clock port, so time-dependent rules (licence state, token expiry) are testable."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current wall-clock time, timezone-aware UTC."""
        ...

    def monotonic(self) -> float:
        """Seconds from an arbitrary origin; never goes backwards."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class ManualClock:
    """Deterministic clock for tests: time moves only when told to."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("start must be timezone-aware")
        self._now = start.astimezone(UTC)
        self._mono = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, *, seconds: float = 0, days: float = 0) -> None:
        delta = timedelta(seconds=seconds, days=days)
        if delta < timedelta(0):
            raise ValueError("a clock only moves forward")
        self._now += delta
        self._mono += delta.total_seconds()

    def set(self, value: datetime) -> None:
        value = value.astimezone(UTC)
        if value < self._now:
            raise ValueError("a clock only moves forward")
        self.advance(seconds=(value - self._now).total_seconds())
