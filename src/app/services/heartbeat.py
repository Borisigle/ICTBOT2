"""Placeholder service functions executed by the scheduler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def log_heartbeat() -> None:
    """Emit a heartbeat log entry.

    Attach to the scheduler when real jobs are available.
    """

    logger.debug("Scheduler heartbeat at %s", datetime.now(timezone.utc).isoformat())
