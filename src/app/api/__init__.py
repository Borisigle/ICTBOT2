"""API routing setup."""

from fastapi import APIRouter

from .market_data import router as market_data_router
from .routes import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(market_data_router)

__all__ = ["api_router"]
