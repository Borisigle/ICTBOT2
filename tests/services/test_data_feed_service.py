from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.data_feed.service import DataFeedService
from app.services.data_feed.types import ARGENTINA_TIMEZONE, OhlcvCandle, Timeframe, TradeTick


class MockProvider:
    def __init__(
        self,
        candles_by_timeframe: dict[Timeframe, list[OhlcvCandle]],
        ticks: list[TradeTick],
    ) -> None:
        self._candles_by_timeframe = candles_by_timeframe
        self._ticks = ticks
        self.closed = False

    async def fetch_recent_candles(
        self, symbol: str, timeframe: Timeframe, limit: int
    ) -> list[OhlcvCandle]:
        return list(self._candles_by_timeframe.get(timeframe, []))[:limit]

    async def stream_trades(self, symbol: str):  # noqa: ANN201 - async generator
        for tick in self._ticks:
            yield tick
        await asyncio.sleep(0)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_data_feed_service_exposes_snapshot() -> None:
    open_time = datetime(2024, 1, 1, 9, 0, tzinfo=ARGENTINA_TIMEZONE)
    seed_candle = OhlcvCandle(
        symbol="BTCUSDT",
        timeframe=Timeframe.MINUTE_1,
        open_time=open_time,
        close_time=open_time + Timeframe.MINUTE_1.duration,
        open=99.0,
        high=101.0,
        low=98.5,
        close=100.5,
        volume=1.5,
    )

    ticks = [
        TradeTick(
            symbol="BTCUSDT",
            price=101.0,
            quantity=0.2,
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=None),
        ),
        TradeTick(
            symbol="BTCUSDT",
            price=102.25,
            quantity=0.3,
            timestamp=datetime(2024, 1, 1, 12, 1, tzinfo=timezone.utc),
        ),
    ]

    provider = MockProvider(
        candles_by_timeframe={
            Timeframe.MINUTE_1: [seed_candle],
            Timeframe.HOUR_1: [],
        },
        ticks=ticks,
    )

    service = DataFeedService(
        provider=provider,
        symbol="BTCUSDT",
        timeframes=[Timeframe.MINUTE_1, Timeframe.HOUR_1],
        history_limit=10,
        tick_buffer_size=5,
    )

    await service.start()
    await asyncio.sleep(0.05)

    snapshot_full = service.snapshot()
    assert snapshot_full["symbol"] == "BTCUSDT"
    assert snapshot_full["latest_tick"]["price"] == pytest.approx(102.25)
    assert len(snapshot_full["recent_ticks"]) == 2
    assert snapshot_full["recent_ticks"][-1]["timestamp"].endswith("-03:00")
    assert "1m" in snapshot_full["ohlcv"]
    assert snapshot_full["ohlcv"]["1m"]

    snapshot_filtered = service.snapshot(max_ticks=1)
    assert len(snapshot_filtered["recent_ticks"]) == 1
    assert snapshot_filtered["recent_ticks"][0]["price"] == pytest.approx(102.25)

    await service.stop()
    assert provider.closed is True


__all__ = ["test_data_feed_service_exposes_snapshot"]
