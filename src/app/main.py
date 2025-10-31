"""FastAPI application bootstrap."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import api_router
from .core.config import get_settings
from .core.logging import configure_logging
from .core.scheduler import AppScheduler
from .services.heartbeat import log_heartbeat


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown hooks."""

    settings = get_settings()
    configure_logging(settings.log_level)

    scheduler = AppScheduler(interval_seconds=settings.scheduler_interval_seconds)
    scheduler.register(log_heartbeat)
    await scheduler.start()

    app.state.settings = settings
    app.state.scheduler = scheduler

    try:
        yield
    finally:
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
