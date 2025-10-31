"""Shared types for the market data feed service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

ARGENTINA_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class Timeframe(Enum):
    """Supported aggregation timeframes."""

    MINUTE_1 = ("1m", timedelta(minutes=1))
    MINUTE_5 = ("5m", timedelta(minutes=5))
    MINUTE_15 = ("15m", timedelta(minutes=15))
    HOUR_1 = ("1h", timedelta(hours=1))
    HOUR_4 = ("4h", timedelta(hours=4))
    DAY_1 = ("1d", timedelta(days=1))

    @property
    def interval(self) -> str:
        """Return the exchange interval label."""

        return self.value[0]

    @property
    def duration(self) -> timedelta:
        """Return the duration of the timeframe."""

        return self.value[1]

    @classmethod
    def default_sequence(cls) -> tuple["Timeframe", ...]:
        """Return the default sequence of timeframes to aggregate."""

        return (
            cls.MINUTE_1,
            cls.MINUTE_5,
            cls.MINUTE_15,
            cls.HOUR_1,
            cls.HOUR_4,
            cls.DAY_1,
        )


@dataclass(slots=True)
class TradeTick:
    """Represents a single trade tick emitted by an exchange."""

    symbol: str
    price: float
    quantity: float
    timestamp: datetime

    def as_dict(self) -> dict[str, object]:
        """Serialize the tick into a JSON-friendly structure."""

        return {
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(slots=True)
class OhlcvCandle:
    """Represents a single OHLCV candle for a timeframe."""

    symbol: str
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self) -> dict[str, object]:
        """Serialize the candle into a JSON-friendly structure."""

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.interval,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


__all__ = ["ARGENTINA_TIMEZONE", "OhlcvCandle", "Timeframe", "TradeTick"]
