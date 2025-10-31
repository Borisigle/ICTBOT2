"""Exchange data provider implementations."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Protocol

import httpx

try:  # pragma: no cover - optional dependency at runtime
    import websockets
    from websockets.legacy.client import Connect, WebSocketClientProtocol
except ImportError as exc:  # pragma: no cover - handled during dependency resolution
    raise RuntimeError("websockets dependency is required for the data feed service") from exc

from .rate_limit import AsyncRateLimiter
from .types import ARGENTINA_TIMEZONE, OhlcvCandle, Timeframe, TradeTick

logger = logging.getLogger(__name__)

WsFactory = Callable[[str], Connect]


class DataProvider(Protocol):
    """Protocol representing the required provider contract."""

    async def fetch_recent_candles(
        self, symbol: str, timeframe: Timeframe, limit: int
    ) -> list[OhlcvCandle]:
        """Fetch recent OHLCV candles for the symbol/timeframe pair."""

    async def stream_trades(self, symbol: str) -> AsyncIterator[TradeTick]:
        """Stream live trade ticks for the symbol."""

    async def close(self) -> None:
        """Release any underlying resources."""


class BinanceDataProvider:
    """REST/WebSocket client for Binance market data."""

    BASE_REST_URL = "https://api.binance.com"
    BASE_WS_URL = "wss://stream.binance.com:9443/ws"
    MAX_BACKOFF_SECONDS = 30.0

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        ws_factory: WsFactory | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
    ) -> None:
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(base_url=self.BASE_REST_URL, timeout=10.0)
        self._ws_factory = ws_factory or websockets.connect
        self._rate_limiter = rate_limiter or AsyncRateLimiter(max_calls=8, period=1.0)

    async def fetch_recent_candles(
        self, symbol: str, timeframe: Timeframe, limit: int
    ) -> list[OhlcvCandle]:
        symbol = symbol.upper()
        params = {
            "symbol": symbol,
            "interval": timeframe.interval,
            "limit": limit,
        }

        async with self._rate_limiter:
            response = await self._http_client.get("/api/v3/klines", params=params)
        response.raise_for_status()

        payload = response.json()
        candles: list[OhlcvCandle] = []
        for entry in payload:
            open_time = datetime.fromtimestamp(entry[0] / 1000, tz=timezone.utc).astimezone(
                ARGENTINA_TIMEZONE
            )
            close_time = datetime.fromtimestamp(entry[6] / 1000, tz=timezone.utc).astimezone(
                ARGENTINA_TIMEZONE
            )
            candle = OhlcvCandle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open=float(entry[1]),
                high=float(entry[2]),
                low=float(entry[3]),
                close=float(entry[4]),
                volume=float(entry[5]),
            )
            candles.append(candle)
        return candles

    async def stream_trades(self, symbol: str) -> AsyncIterator[TradeTick]:
        stream_symbol = symbol.lower()
        stream = f"{stream_symbol}@trade"
        url = f"{self.BASE_WS_URL}/{stream}"
        backoff = 1.0

        while True:
            try:
                async with self._ws_factory(url) as websocket:
                    async for tick in self._consume_stream(symbol, websocket):
                        yield tick
                    backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - log and retry to maintain the stream
                logger.warning("Trade stream error for %s: %s", symbol, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.MAX_BACKOFF_SECONDS)

    async def _consume_stream(
        self, symbol: str, websocket: WebSocketClientProtocol
    ) -> AsyncIterator[TradeTick]:
        async for message in websocket:
            payload = json.loads(message)
            tick = TradeTick(
                symbol=symbol.upper(),
                price=float(payload["p"]),
                quantity=float(payload["q"]),
                timestamp=datetime.fromtimestamp(payload["T"] / 1000, tz=timezone.utc).astimezone(
                    ARGENTINA_TIMEZONE
                ),
            )
            yield tick

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()


class ProviderFactory:
    """Factory helper to instantiate configured providers."""

    @staticmethod
    def create(provider_name: str) -> DataProvider:
        normalized = provider_name.strip().lower()
        if normalized == "binance":
            return BinanceDataProvider()
        if normalized == "bybit":  # pragma: no cover - placeholder for future expansion
            msg = "Bybit provider not yet implemented"
            raise NotImplementedError(msg)

        msg = f"Unsupported market data provider '{provider_name}'"
        raise ValueError(msg)


__all__ = ["BinanceDataProvider", "DataProvider", "ProviderFactory"]
