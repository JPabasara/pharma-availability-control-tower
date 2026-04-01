"""Business-time helpers for the 48-hour planning horizon."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apps.api.app.dependencies.config import settings


def get_business_timezone() -> ZoneInfo:
    """Return the configured business timezone."""
    return ZoneInfo(settings.BUSINESS_TIMEZONE)


def get_business_now() -> datetime:
    """Return the current time in the configured business timezone."""
    return datetime.now(timezone.utc).astimezone(get_business_timezone())


def get_planning_dates() -> list[date]:
    """Return the two business dates that define the current planning horizon."""
    business_today = get_business_now().date()
    return [business_today, business_today + timedelta(days=1)]
