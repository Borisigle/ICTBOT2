"""Application logging configuration."""

from __future__ import annotations

import copy
import logging
from logging.config import dictConfig
from typing import Any

LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s | %(levelprefix)s | %(name)s | %(message)s",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": "%(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "uvicorn.access": {
            "class": "logging.StreamHandler",
            "formatter": "access",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {
            "handlers": ["uvicorn.access"],
            "level": "INFO",
            "propagate": False,
        },
        "app": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["default"], "level": "INFO"},
}


def configure_logging(level: str | int = "INFO") -> None:
    """Configure the logging subsystem for the application."""

    config = copy.deepcopy(LOGGING_CONFIG)
    config["root"]["level"] = level

    # Ensure the FastAPI/uvicorn related loggers follow the requested level as well.
    for logger_name in ("uvicorn", "uvicorn.error", "app"):
        config["loggers"].setdefault(logger_name, {"handlers": ["default"], "propagate": False})
        config["loggers"][logger_name]["level"] = level

    dictConfig(config)
    logging.getLogger(__name__).debug("Logging configured with level %s", level)
