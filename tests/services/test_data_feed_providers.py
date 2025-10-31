from __future__ import annotations

import json

import pytest

from app.services.data_feed.providers import BinanceDataProvider
from app.services.data_feed.types import ARGENTINA_TIMEZONE, Timeframe


class StubResponse:
    def __init__(self, payload: list[list[object]]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[list[object]]:
        return self._payload


class StubAsyncClient:
    def __init__(self, payload: list[list[object]]) -> None:
        self._payload = payload
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    async def get(self, url: str, params: dict[str, object]) -> StubResponse:
        self.calls.append((url, params))
        return StubResponse(self._payload)

    async def aclose(self) -> None:
        self.closed = True


class StubWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)

    def __aiter__(self) -> "StubWebSocket":
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration as exc:  # pragma: no cover - loop termination
            raise StopAsyncIteration from exc


class StubConnection:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    async def __aenter__(self) -> StubWebSocket:
        return StubWebSocket(list(self._messages))

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001 - context protocol signature
        return False


class StubWsFactory:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages
        self.calls: list[str] = []

    def __call__(self, url: str) -> StubConnection:
        self.calls.append(url)
        return StubConnection(list(self._messages))


@pytest.mark.asyncio
async def test_binance_fetch_recent_candles_respects_timezone() -> None:
    open_time_ms = 1_720_000_000_000
    close_time_ms = open_time_ms + 60_000
    payload = [[open_time_ms, "100", "105", "99", "104", "12.5", close_time_ms]]
    client = StubAsyncClient(payload)
    provider = BinanceDataProvider(http_client=client)

    candles = await provider.fetch_recent_candles("BTCUSDT", Timeframe.MINUTE_1, limit=1)

    assert len(candles) == 1
    candle = candles[0]
    assert candle.open == 100.0
    assert candle.close == 104.0
    assert candle.open_time.tzinfo is not None
    assert candle.open_time.tzinfo.key == ARGENTINA_TIMEZONE.key
    assert client.calls[0][1]["symbol"] == "BTCUSDT"

    await provider.close()
    # Provider should not close the client it does not own
    assert client.closed is False


@pytest.mark.asyncio
async def test_binance_stream_trades_yields_ticks() -> None:
    message = json.dumps({"p": "55000.12", "q": "0.010", "T": 1_720_000_060_000})
    ws_factory = StubWsFactory(messages=[message])
    provider = BinanceDataProvider(ws_factory=ws_factory)

    stream = provider.stream_trades("BTCUSDT")
    tick = await anext(stream)
    assert tick.price == pytest.approx(55000.12)
    assert tick.quantity == pytest.approx(0.01)
    assert tick.timestamp.tzinfo is not None
    assert tick.timestamp.tzinfo.key == ARGENTINA_TIMEZONE.key
    assert ws_factory.calls[0].endswith("btcusdt@trade")

    await stream.aclose()
    await provider.close()


__all__ = [
    "test_binance_fetch_recent_candles_respects_timezone",
    "test_binance_stream_trades_yields_ticks",
]
