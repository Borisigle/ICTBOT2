"""Lightweight asynchronous scheduler placeholder."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

Callback = Callable[[], Any | Awaitable[Any]]


class AppScheduler:
    """A minimal background scheduler intended to be extended with real jobs."""

    def __init__(self, interval_seconds: int = 300) -> None:
        self.interval_seconds = interval_seconds
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._callbacks: list[Callback] = []

    def register(self, callback: Callback) -> None:
        """Register a callback to execute on each heartbeat."""

        self._callbacks.append(callback)
        logger.debug("Registered scheduler callback %s", callback)

    async def start(self) -> None:
        """Start the scheduler loop if it is not already running."""

        if self._task and not self._task.done():
            logger.debug("Scheduler already running; skipping start")
            return

        self._shutdown_event = asyncio.Event()
        self._task = asyncio.create_task(self._runner())
        logger.info("Scheduler started with interval=%s seconds", self.interval_seconds)

    async def shutdown(self) -> None:
        """Signal the background loop to stop and wait for termination."""

        if not self._task:
            return

        self._shutdown_event.set()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        logger.info("Scheduler stopped")

    async def _runner(self) -> None:
        """Execute registered callbacks on the configured cadence."""

        while True:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=float(self.interval_seconds)
                )
                break
            except asyncio.TimeoutError:
                await self._execute_callbacks()
        logger.debug("Scheduler runner exiting")

    async def _execute_callbacks(self) -> None:
        """Run registered callbacks, awaiting them when necessary."""

        if not self._callbacks:
            logger.debug("Scheduler heartbeat (no callbacks registered)")
            return

        for callback in list(self._callbacks):
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001 - bubbling up would stop the loop
                logger.exception("Scheduler callback %s raised an exception", callback)
