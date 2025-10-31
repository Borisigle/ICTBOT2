"""Application configuration management."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load environment variables early to support tools that do not rely on Pydantic directly.
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()


class Settings(BaseSettings):
    """Defines environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")

    app_name: str = Field(default="Bootstrap FastAPI Service", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    default_timezone: str = Field(default="America/New_York", alias="APP_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    service_api_key: str | None = Field(default=None, alias="SERVICE_API_KEY")
    scheduler_interval_seconds: int = Field(
        default=300, alias="BACKGROUND_POLL_INTERVAL_SECONDS"
    )

    market_data_enabled: bool = Field(default=True, alias="MARKET_DATA_ENABLED")
    market_data_provider: str = Field(default="binance", alias="MARKET_DATA_PROVIDER")
    market_data_symbol: str = Field(default="BTCUSDT", alias="MARKET_DATA_SYMBOL")
    market_data_timezone: str = Field(
        default="America/Argentina/Buenos_Aires", alias="MARKET_DATA_TIMEZONE"
    )
    market_data_history_limit: int = Field(
        default=500, alias="MARKET_DATA_HISTORY_LIMIT"
    )
    market_data_tick_buffer_size: int = Field(
        default=1000, alias="MARKET_DATA_TICK_BUFFER_SIZE"
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
