"""FastAPI application bootstrap."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from .api import api_router
from .core.config import get_settings
from .core.logging import configure_logging
from .core.scheduler import AppScheduler
from .services.data_feed import DataFeedService
from .services.heartbeat import log_heartbeat


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown hooks."""

    settings = get_settings()
    configure_logging(settings.log_level)

    scheduler = AppScheduler(interval_seconds=settings.scheduler_interval_seconds)
    scheduler.register(log_heartbeat)
    await scheduler.start()

    data_feed_service: DataFeedService | None = None
    if settings.market_data_enabled:
        candidate_service: DataFeedService | None = None
        try:
            candidate_service = DataFeedService.from_settings(
                settings.market_data_provider,
                symbol=settings.market_data_symbol,
                history_limit=settings.market_data_history_limit,
                tick_buffer_size=settings.market_data_tick_buffer_size,
                timezone_name=settings.market_data_timezone,
            )
            await candidate_service.start()
        except Exception:  # noqa: BLE001 - log error and continue startup
            logger.exception("Failed to start market data feed service")
            if candidate_service is not None:
                await candidate_service.stop()
        else:
            data_feed_service = candidate_service

    app.state.settings = settings
    app.state.scheduler = scheduler
    app.state.data_feed_service = data_feed_service

    try:
        yield
    finally:
        if data_feed_service is not None:
            await data_feed_service.stop()
        await scheduler.shutdown()


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
