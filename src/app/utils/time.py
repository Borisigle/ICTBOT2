"""Time zone conversion helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN_TIME = ZoneInfo("America/New_York")
UTC_MINUS_THREE = timezone(timedelta(hours=-3))


def ensure_eastern(dt: datetime) -> datetime:
    """Return a timezone-aware datetime localized to Eastern Time."""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=EASTERN_TIME)
    return dt.astimezone(EASTERN_TIME)


def current_eastern_time() -> datetime:
    """Return the current datetime in Eastern Time."""

    return datetime.now(tz=EASTERN_TIME)


def convert_eastern_to_utc_minus_three(dt: datetime) -> datetime:
    """Convert a datetime from EST/EDT (Eastern Time) to UTC−3."""

    eastern_dt = ensure_eastern(dt)
    return eastern_dt.astimezone(UTC_MINUS_THREE)


def convert_utc_minus_three_to_eastern(dt: datetime) -> datetime:
    """Convert a datetime from UTC−3 back to Eastern Time."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_MINUS_THREE)
    return dt.astimezone(EASTERN_TIME)
