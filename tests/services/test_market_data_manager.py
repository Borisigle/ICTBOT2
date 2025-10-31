from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.data_feed.market_data_manager import MarketDataManager
from app.services.data_feed.types import ARGENTINA_TIMEZONE, OhlcvCandle, Timeframe, TradeTick


def make_tick(price: float, quantity: float, hour: int, minute: int, second: int = 0) -> TradeTick:
    timestamp = datetime(2024, 1, 1, hour, minute, second, tzinfo=timezone.utc)
    return TradeTick(symbol="BTCUSDT", price=price, quantity=quantity, timestamp=timestamp)


class RecordingScheduler:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[], None]] = []

    def register(self, callback: Callable[[], None]) -> None:  # pragma: no cover - simple helper
        self.callbacks.append(callback)


def test_manager_ingests_ticks_and_exposes_slices() -> None:
    manager = MarketDataManager(
        symbol="BTCUSDT",
        timeframes=(Timeframe.MINUTE_1, Timeframe.MINUTE_5),
        history_limit=10,
    )

    ticks = [
        make_tick(100.0, 0.25, hour=15, minute=0),
        make_tick(102.0, 0.10, hour=15, minute=0, second=30),
        make_tick(101.5, 0.30, hour=15, minute=1),
    ]

    for tick in ticks:
        manager.ingest_tick(tick)

    candles_1m = manager.get_slice(Timeframe.MINUTE_1)
    assert len(candles_1m) == 2
    assert candles_1m[0].open == pytest.approx(100.0)
    assert candles_1m[0].close == pytest.approx(102.0)
    assert candles_1m[1].open == pytest.approx(101.5)

    candles_5m = manager.get_slice(Timeframe.MINUTE_5)
    assert len(candles_5m) == 1
    combined = candles_5m[0]
    assert combined.high == pytest.approx(102.0)
    assert combined.volume == pytest.approx(0.65)

    rolling_high = manager.get_rolling_high(Timeframe.MINUTE_1, window=2)
    rolling_low = manager.get_rolling_low(Timeframe.MINUTE_1, window=2)
    assert rolling_high == pytest.approx(102.0)
    assert rolling_low == pytest.approx(100.0)

    latest = manager.get_latest(Timeframe.MINUTE_5)
    assert latest is not None
    assert latest.close == pytest.approx(101.5)


def test_manager_persists_and_recovers_state(tmp_path: Path) -> None:
    state_path = tmp_path / "btc_state.json"
    manager = MarketDataManager(
        symbol="BTCUSDT",
        timeframes=(Timeframe.MINUTE_1,),
        history_limit=5,
        persist_path=state_path,
    )

    open_time = datetime(2024, 1, 1, 12, 0, tzinfo=ARGENTINA_TIMEZONE)
    close_time = open_time + Timeframe.MINUTE_1.duration
    candle = OhlcvCandle(
        symbol="BTCUSDT",
        timeframe=Timeframe.MINUTE_1,
        open_time=open_time,
        close_time=close_time,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1.25,
    )

    manager.seed(Timeframe.MINUTE_1, [candle])
    assert state_path.exists()

    restored = MarketDataManager(
        symbol="BTCUSDT",
        timeframes=(Timeframe.MINUTE_1,),
        history_limit=5,
        persist_path=state_path,
    )

    latest = restored.get_latest(Timeframe.MINUTE_1)
    assert latest is not None
    assert latest.open == pytest.approx(100.0)
    assert latest.open_time == open_time


def test_scheduler_refresh_rehydrates_cache(tmp_path: Path) -> None:
    scheduler = RecordingScheduler()
    manager = MarketDataManager(
        symbol="BTCUSDT",
        timeframes=(Timeframe.MINUTE_1, Timeframe.MINUTE_5),
        history_limit=5,
        persist_path=tmp_path / "state.json",
        scheduler=scheduler,
    )

    assert scheduler.callbacks
    assert scheduler.callbacks[0].__self__ is manager

    tick = make_tick(200.0, 0.5, hour=16, minute=5)
    manager.ingest_tick(tick)

    manager._cache[Timeframe.MINUTE_1] = []  # type: ignore[attr-defined]
    assert manager.get_slice(Timeframe.MINUTE_1) == []

    scheduler.callbacks[0]()
    refreshed = manager.get_slice(Timeframe.MINUTE_1)
    assert len(refreshed) == 1
    assert refreshed[0].open == pytest.approx(200.0)
