"""API route definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings
from ..utils.time import convert_eastern_to_utc_minus_three, current_eastern_time

router = APIRouter()


@router.get("/health", tags=["health"])
async def healthcheck(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Simple health endpoint with timestamp metadata."""

    eastern_now = current_eastern_time()
    target_now = convert_eastern_to_utc_minus_three(eastern_now)

    return {
        "status": "ok",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timezone": settings.default_timezone,
        "timestamp_eastern": eastern_now.isoformat(),
        "timestamp_utc_minus_three": target_now.isoformat(),
    }
