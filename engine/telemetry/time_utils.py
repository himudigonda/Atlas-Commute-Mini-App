import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

logger = structlog.get_logger()

# Default to the system timezone or a configured one
DEFAULT_TZ_KEY = os.getenv("APP_TIMEZONE", "America/Los_Angeles").strip('"')


def _get_tz() -> ZoneInfo:
    """Safely retrieves the ZoneInfo object with fallbacks."""
    try:
        return ZoneInfo(DEFAULT_TZ_KEY)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("time.tz_not_found", requested=DEFAULT_TZ_KEY, fallback="UTC")
        return ZoneInfo("UTC")


def get_now() -> datetime:
    """Returns a timezone-aware datetime object for the configured timezone."""
    return datetime.now(_get_tz())


def format_now() -> str:
    """Returns a formatted string of the current time with timezone info."""
    now = get_now()
    return now.strftime("%A, %Y-%m-%d %H:%M:%S %Z")


def to_local(dt: datetime) -> datetime:
    """Converts a naive or aware datetime to the local configured timezone."""
    tz = _get_tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
