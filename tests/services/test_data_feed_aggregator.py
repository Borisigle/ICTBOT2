from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.data_feed.aggregator import OhlcvAggregator
from app.services.data_feed.types import ARGENTINA_TIMEZONE, Timeframe, TradeTick


def make_tick(price: float, quantity: float, hour: int, minute: int, second: int = 0) -> TradeTick:
    timestamp = datetime(2024, 1, 1, hour, minute, second, tzinfo=timezone.utc)
    return TradeTick(symbol="BTCUSDT", price=price, quantity=quantity, timestamp=timestamp)


def test_aggregator_updates_candles_across_timeframes() -> None:
    aggregator = OhlcvAggregator(
        symbol="BTCUSDT",
        timeframes=[Timeframe.MINUTE_1, Timeframe.MINUTE_5],
        max_length=10,
    )

    first_tick = make_tick(100.0, 0.25, hour=15, minute=0)
    second_tick = make_tick(102.0, 0.10, hour=15, minute=0, second=30)
    third_tick = make_tick(101.5, 0.30, hour=15, minute=1)

    aggregator.update(first_tick)
    aggregator.update(second_tick)
    aggregator.update(third_tick)

    candles_1m = aggregator.get_candles(Timeframe.MINUTE_1)
    assert len(candles_1m) == 2

    first_candle = candles_1m[0]
    assert first_candle.open == 100.0
    assert first_candle.close == 102.0
    assert first_candle.high == 102.0
    assert first_candle.low == 100.0
    assert first_candle.volume == pytest.approx(0.35)
    assert first_candle.open_time.tzinfo is not None
    assert first_candle.open_time.tzinfo.key == ARGENTINA_TIMEZONE.key

    second_candle = candles_1m[1]
    assert second_candle.open == 101.5
    assert second_candle.close == 101.5
    assert second_candle.volume == pytest.approx(0.30)

    candles_5m = aggregator.get_candles(Timeframe.MINUTE_5)
    assert len(candles_5m) == 1
    combined_candle = candles_5m[0]
    assert combined_candle.open == 100.0
    assert combined_candle.close == 101.5
    assert combined_candle.volume == pytest.approx(0.65)
    assert combined_candle.open_time.tzinfo.key == ARGENTINA_TIMEZONE.key


__all__ = ["test_aggregator_updates_candles_across_timeframes"]
