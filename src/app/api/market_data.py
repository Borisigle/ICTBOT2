"""Market data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..services.data_feed import DataFeedService

router = APIRouter(prefix="/market-data", tags=["market-data"])


def get_data_feed_service(request: Request) -> DataFeedService:
    service = getattr(request.app.state, "data_feed_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Market data feed is not available")
    return service


@router.get("/{symbol}")
async def market_data_snapshot(
    symbol: str,
    max_ticks: int | None = Query(None, ge=1, le=1000),
    service: DataFeedService = Depends(get_data_feed_service),
) -> dict[str, object]:
    """Return the current market data snapshot for the requested symbol."""

    if symbol.upper() != service.symbol:
        raise HTTPException(status_code=404, detail="Symbol not tracked")

    return service.snapshot(max_ticks=max_ticks)


__all__ = ["router"]
