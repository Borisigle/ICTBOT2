"""OHLCV aggregation utilities for the market data feed."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Deque, Iterable
from zoneinfo import ZoneInfo

from .types import ARGENTINA_TIMEZONE, OhlcvCandle, Timeframe, TradeTick


def _floor_timestamp(dt: datetime, delta: timedelta, tz: ZoneInfo) -> datetime:
    """Floor the datetime to the start of the timeframe within the provided timezone."""

    localized = dt.astimezone(tz)
    seconds = int(delta.total_seconds())
    timestamp = int(localized.timestamp())
    floored = timestamp - (timestamp % seconds)
    return datetime.fromtimestamp(floored, tz=tz)


class OhlcvAggregator:
    """Aggregate trade ticks into OHLCV candles across multiple timeframes."""

    def __init__(
        self,
        symbol: str,
        timeframes: Iterable[Timeframe],
        max_length: int = 500,
        timezone_: ZoneInfo = ARGENTINA_TIMEZONE,
    ) -> None:
        self._symbol = symbol.upper()
        self._timezone = timezone_
        self._buffers: dict[Timeframe, Deque[OhlcvCandle]] = {
            timeframe: deque(maxlen=max_length) for timeframe in timeframes
        }

    @property
    def timezone(self) -> ZoneInfo:
        """Return the timezone used by the aggregator."""

        return self._timezone

    def seed(self, timeframe: Timeframe, candles: Iterable[OhlcvCandle]) -> None:
        """Seed the buffer for a timeframe with historical candles."""

        buffer = self._buffers[timeframe]
        buffer.clear()
        for candle in sorted(candles, key=lambda c: c.open_time):
            normalized = self._ensure_timezone(candle)
            buffer.append(normalized)

    def update(self, tick: TradeTick) -> None:
        """Update all timeframe buffers based on the provided trade tick."""

        localized_tick = self._localize_tick(tick)

        for timeframe, buffer in self._buffers.items():
            self._upsert_candle(buffer, timeframe, localized_tick)

    def get_candles(self, timeframe: Timeframe) -> list[OhlcvCandle]:
        """Return the current candles for the requested timeframe."""

        buffer = self._buffers[timeframe]
        return list(buffer)

    def _ensure_timezone(self, candle: OhlcvCandle) -> OhlcvCandle:
        """Ensure a candle uses the aggregator timezone."""

        if candle.open_time.tzinfo is None or candle.close_time.tzinfo is None:
            raise ValueError("OHLCV candles must be timezone aware")

        if candle.open_time.tzinfo == self._timezone and candle.close_time.tzinfo == self._timezone:
            return candle

        return replace(
            candle,
            open_time=candle.open_time.astimezone(self._timezone),
            close_time=candle.close_time.astimezone(self._timezone),
        )

    def _localize_tick(self, tick: TradeTick) -> TradeTick:
        if tick.timestamp.tzinfo is None:
            message = "Trade ticks must include timezone-aware timestamps"
            raise ValueError(message)

        if tick.timestamp.tzinfo == self._timezone:
            return tick

        return replace(tick, timestamp=tick.timestamp.astimezone(self._timezone))

    def _upsert_candle(
        self,
        buffer: Deque[OhlcvCandle],
        timeframe: Timeframe,
        tick: TradeTick,
    ) -> None:
        frame_start = _floor_timestamp(tick.timestamp, timeframe.duration, self._timezone)
        frame_end = frame_start + timeframe.duration

        if buffer and buffer[-1].open_time == frame_start:
            candle = buffer[-1]
            candle.high = max(candle.high, tick.price)
            candle.low = min(candle.low, tick.price)
            candle.close = tick.price
            candle.volume += tick.quantity
            candle.close_time = frame_end
            return

        new_candle = OhlcvCandle(
            symbol=self._symbol,
            timeframe=timeframe,
            open_time=frame_start,
            close_time=frame_end,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.quantity,
        )
        buffer.append(new_candle)


__all__ = ["OhlcvAggregator"]
