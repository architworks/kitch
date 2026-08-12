"""Authoritative household calendar helpers for dated meal planning."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_HOUSEHOLD_TIMEZONE = "Asia/Kolkata"


def household_zone(timezone_name: str | None) -> ZoneInfo:
    name = str(timezone_name or DEFAULT_HOUSEHOLD_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown household timezone: {name}") from error


def parse_iso_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as error:
        raise ValueError(f"Expected an ISO calendar date, got: {value!r}") from error


def monday_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


def dates_between(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    return [start + timedelta(days=index) for index in range((end - start).days + 1)]


def calendar_context(
    timezone_name: str | None,
    reference: datetime | None = None,
) -> dict[str, Any]:
    zone = household_zone(timezone_name)
    now = reference.astimezone(zone) if reference else datetime.now(zone)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    current_week_start = monday_for(today)
    current_week_end = current_week_start + timedelta(days=6)
    next_week_start = current_week_start + timedelta(days=7)
    next_week_end = next_week_start + timedelta(days=6)

    def describe_range(start: date, end: date) -> str:
        return "; ".join(
            item.strftime("%A, %B %d, %Y (%Y-%m-%d)")
            for item in dates_between(start, end)
        )

    return {
        "timezone": zone.key,
        "now": now,
        "today": today,
        "tomorrow": tomorrow,
        "current_week_start": current_week_start,
        "current_week_end": current_week_end,
        "next_week_start": next_week_start,
        "next_week_end": next_week_end,
        "current_week_dates": describe_range(current_week_start, current_week_end),
        "next_week_dates": describe_range(next_week_start, next_week_end),
    }
