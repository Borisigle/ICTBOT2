"""High level data feed service coordinating providers and aggregation."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import replace
from datetime import timezone
from typing import Deque
from zoneinfo import ZoneInfo

from .aggregator import OhlcvAggregator
from .providers import DataProvider, ProviderFactory
from .types import ARGENTINA_TIMEZONE, Timeframe, TradeTick

logger = logging.getLogger(__name__)


class DataFeedService:
    """Coordinate streaming market data and expose aggregated views."""

    def __init__(
        self,
        *,
        provider: DataProvider,
        symbol: str,
        timeframes: Sequence[Timeframe],
        history_limit: int,
        tick_buffer_size: int,
        timezone_: ZoneInfo = ARGENTINA_TIMEZONE,
    ) -> None:
        self._provider = provider
        self._symbol = symbol.upper()
        self._timeframes = tuple(timeframes)
        self._history_limit = history_limit
        self._tick_buffer_size = tick_buffer_size
        self._aggregator = OhlcvAggregator(
            symbol=self._symbol,
            timeframes=self._timeframes,
            max_length=history_limit,
            timezone_=timezone_,
        )
        self._recent_ticks: Deque[TradeTick] = deque(maxlen=tick_buffer_size)
        self._latest_tick: TradeTick | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def symbol(self) -> str:
        """Return the symbol tracked by the service."""

        return self._symbol

    @classmethod
    def from_settings(
        cls,
        provider_name: str,
        *,
        symbol: str,
        timeframes: Sequence[Timeframe] | None = None,
        history_limit: int = 500,
        tick_buffer_size: int = 1000,
        timezone_name: str = ARGENTINA_TIMEZONE.key,
    ) -> "DataFeedService":
        """Instantiate the service from configuration values."""

        provider = ProviderFactory.create(provider_name)
        resolved_timeframes = timeframes or Timeframe.default_sequence()
        timezone_ = ZoneInfo(timezone_name)
        return cls(
            provider=provider,
            symbol=symbol,
            timeframes=resolved_timeframes,
            history_limit=history_limit,
            tick_buffer_size=tick_buffer_size,
            timezone_=timezone_,
        )

    async def start(self) -> None:
        """Start streaming market data."""

        async with self._lock:
            if self._task and not self._task.done():
                logger.debug("Data feed service already running")
                return

            await self._seed_history()
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="data-feed-runner")
            logger.info("Data feed service started for %s", self._symbol)

    async def stop(self) -> None:
        """Stop the streaming task and release resources."""

        async with self._lock:
            if not self._task:
                await self._provider.close()
                return

            self._stop_event.set()
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            await self._provider.close()
            logger.info("Data feed service stopped for %s", self._symbol)

    def snapshot(self, *, max_ticks: int | None = None) -> dict[str, object]:
        """Return a serializable snapshot of the current feed state."""

        ticks = list(self._recent_ticks)
        if max_ticks is not None:
            if max_ticks <= 0:
                ticks = []
            else:
                ticks = ticks[-max_ticks:]

        return {
            "symbol": self._symbol,
            "latest_tick": self._latest_tick.as_dict() if self._latest_tick else None,
            "recent_ticks": [tick.as_dict() for tick in ticks],
            "ohlcv": {
                timeframe.interval: [candle.as_dict() for candle in self._aggregator.get_candles(timeframe)]
                for timeframe in self._timeframes
            },
        }

    async def _seed_history(self) -> None:
        logger.debug("Seeding historical candles for %s", self._symbol)
        self._recent_ticks.clear()
        self._latest_tick = None
        for timeframe in self._timeframes:
            candles = await self._provider.fetch_recent_candles(
                self._symbol, timeframe, self._history_limit
            )
            self._aggregator.seed(timeframe, candles)

    async def _run(self) -> None:
        try:
            async for tick in self._provider.stream_trades(self._symbol):
                if self._stop_event.is_set():
                    break
                self._handle_tick(tick)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - surface error while keeping consistent state
            logger.exception("Data feed service experienced an error")
            raise

    def _handle_tick(self, tick: TradeTick) -> None:
        timestamp = tick.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        localized = timestamp.astimezone(self._aggregator.timezone)
        localized_tick = replace(tick, timestamp=localized)
        self._latest_tick = localized_tick
        self._recent_ticks.append(localized_tick)
        self._aggregator.update(localized_tick)


__all__ = ["DataFeedService"]
