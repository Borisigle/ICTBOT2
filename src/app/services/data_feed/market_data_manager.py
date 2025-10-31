"""Timeframe engine and state manager for market data aggregation."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

from ...core.scheduler import AppScheduler
from .aggregator import OhlcvAggregator
from .types import ARGENTINA_TIMEZONE, OhlcvCandle, Timeframe, TradeTick

logger = logging.getLogger(__name__)


class MarketDataManager:
    """Manage OHLCV candles across multiple timeframes with caching and persistence."""

    def __init__(
        self,
        *,
        symbol: str,
        timeframes: Sequence[Timeframe] | None = None,
        history_limit: int = 500,
        timezone_: ZoneInfo = ARGENTINA_TIMEZONE,
        persist_path: str | Path | None = None,
        scheduler: AppScheduler | None = None,
    ) -> None:
        resolved_timeframes = tuple(timeframes) if timeframes else Timeframe.default_sequence()
        self._symbol = symbol.upper()
        self._timeframes = resolved_timeframes
        self._timezone = timezone_
        self._aggregator = OhlcvAggregator(
            symbol=self._symbol,
            timeframes=self._timeframes,
            max_length=history_limit,
            timezone_=timezone_,
        )
        self._history_limit = history_limit
        self._lock = threading.RLock()
        self._cache: dict[Timeframe, list[OhlcvCandle]] = {tf: [] for tf in self._timeframes}
        self._persist_path = Path(persist_path).expanduser() if persist_path else None
        self._scheduler: AppScheduler | None = None

        self._load_persisted_state()

        if scheduler is not None:
            self.attach_scheduler(scheduler)

    @property
    def symbol(self) -> str:
        """Return the tracked trading symbol."""

        return self._symbol

    @property
    def timeframes(self) -> tuple[Timeframe, ...]:
        """Return the ordered timeframes managed by this instance."""

        return self._timeframes

    def attach_scheduler(self, scheduler: AppScheduler) -> None:
        """Register the refresh hook on the provided scheduler."""

        self._scheduler = scheduler
        scheduler.register(self.refresh_higher_timeframes)
        logger.debug("Scheduler attached to market data manager for %s", self._symbol)

    def seed(self, timeframe: Timeframe, candles: Iterable[OhlcvCandle]) -> None:
        """Seed a timeframe with historical candles."""

        with self._lock:
            self._aggregator.seed(timeframe, candles)
            self._sync_cache_locked()
            self._persist_state_locked()

    def seed_batch(self, payload: dict[Timeframe, Iterable[OhlcvCandle]]) -> None:
        """Seed multiple timeframes with historical candles."""

        for timeframe, candles in payload.items():
            self.seed(timeframe, candles)

    def ingest_tick(self, tick: TradeTick) -> None:
        """Ingest a trade tick and update all tracked timeframes."""

        localized = self._localize_tick(tick)
        with self._lock:
            self._aggregator.update(localized)
            self._sync_cache_locked()
            self._persist_state_locked()

    def refresh_higher_timeframes(self) -> None:
        """Refresh cached candles for higher timeframes via the scheduler hook."""

        with self._lock:
            self._sync_cache_locked()
            self._persist_state_locked()

    def get_latest(self, timeframe: Timeframe) -> OhlcvCandle | None:
        """Return the latest candle for the requested timeframe."""

        with self._lock:
            candles = self._cache.get(timeframe, [])
            return candles[-1] if candles else None

    def get_slice(self, timeframe: Timeframe, *, limit: int | None = None) -> list[OhlcvCandle]:
        """Return a list of recent candles for a timeframe ordered oldest to newest."""

        with self._lock:
            candles = self._cache.get(timeframe, [])
            if not candles:
                return []
            if limit is None or limit >= len(candles):
                return list(candles)
            if limit <= 0:
                return []
            return list(candles[-limit:])

    def get_rolling_high(self, timeframe: Timeframe, window: int) -> float | None:
        """Return the rolling high over the provided candle window."""

        if window <= 0:
            msg = "Window must be a positive integer"
            raise ValueError(msg)

        candles = self.get_slice(timeframe, limit=window)
        if not candles:
            return None
        return max(candle.high for candle in candles)

    def get_rolling_low(self, timeframe: Timeframe, window: int) -> float | None:
        """Return the rolling low over the provided candle window."""

        if window <= 0:
            msg = "Window must be a positive integer"
            raise ValueError(msg)

        candles = self.get_slice(timeframe, limit=window)
        if not candles:
            return None
        return min(candle.low for candle in candles)

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of the cached state."""

        with self._lock:
            return {
                "symbol": self._symbol,
                "timeframes": {
                    timeframe.interval: [candle.as_dict() for candle in self._cache[timeframe]]
                    for timeframe in self._timeframes
                },
            }

    def _sync_cache_locked(self) -> None:
        for timeframe in self._timeframes:
            candles = self._aggregator.get_candles(timeframe)
            if len(candles) > self._history_limit:
                candles = candles[-self._history_limit :]
            self._cache[timeframe] = candles

    def _persist_state_locked(self) -> None:
        if self._persist_path is None:
            return

        snapshot = self.snapshot()
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._persist_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(snapshot, ensure_ascii=False))
            temp_path.replace(self._persist_path)
        except OSError:
            logger.exception("Failed to persist market data state for %s", self._symbol)

    def _load_persisted_state(self) -> None:
        if self._persist_path is None or not self._persist_path.exists():
            return

        try:
            raw = self._persist_path.read_text()
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            logger.exception("Unable to load persisted market data state")
            return

        timeframe_payload = payload.get("timeframes", {})
        with self._lock:
            for timeframe in self._timeframes:
                entries = timeframe_payload.get(timeframe.interval, [])
                if not entries:
                    continue
                candles = [self._deserialize_candle(entry, timeframe) for entry in entries]
                self._aggregator.seed(timeframe, candles)
            self._sync_cache_locked()

    def _deserialize_candle(self, payload: dict[str, Any], timeframe: Timeframe) -> OhlcvCandle:
        try:
            open_time = datetime.fromisoformat(payload["open_time"])
            close_time = datetime.fromisoformat(payload["close_time"])
            return OhlcvCandle(
                symbol=payload["symbol"],
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open=float(payload["open"]),
                high=float(payload["high"]),
                low=float(payload["low"]),
                close=float(payload["close"]),
                volume=float(payload["volume"]),
            )
        except KeyError as exc:
            msg = "Invalid candle payload for timeframe %s" % timeframe.interval
            raise ValueError(msg) from exc

    def _localize_tick(self, tick: TradeTick) -> TradeTick:
        if tick.timestamp.tzinfo is None:
            msg = "Trade tick must contain a timezone-aware timestamp"
            raise ValueError(msg)
        if tick.timestamp.tzinfo == self._timezone:
            return tick
        return TradeTick(
            symbol=tick.symbol,
            price=tick.price,
            quantity=tick.quantity,
            timestamp=tick.timestamp.astimezone(self._timezone),
        )


__all__ = ["MarketDataManager"]
