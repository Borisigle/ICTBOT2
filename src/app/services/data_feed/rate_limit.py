"""Asynchronous rate limiting utilities."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Deque


class AsyncRateLimiter:
    """Simple token bucket style rate limiter for async workflows."""

    def __init__(self, max_calls: int, period: float) -> None:
        if max_calls <= 0:
            msg = "max_calls must be positive"
            raise ValueError(msg)
        if period <= 0:
            msg = "period must be positive"
            raise ValueError(msg)

        self._max_calls = max_calls
        self._period = period
        self._lock = asyncio.Lock()
        self._timestamps: Deque[float] = deque()

    async def acquire(self) -> None:
        """Acquire permission to perform an action respecting the quota."""

        loop = asyncio.get_running_loop()

        while True:
            async with self._lock:
                now = loop.time()
                while self._timestamps and now - self._timestamps[0] >= self._period:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return

                wait_time = self._period - (now - self._timestamps[0])

            await asyncio.sleep(wait_time)

    async def __aenter__(self) -> "AsyncRateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001 - standard context signature
        return None


__all__ = ["AsyncRateLimiter"]
