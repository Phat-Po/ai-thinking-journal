"""Timezone-aware date utilities. All functions accept tz as a parameter."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


def get_tz(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def target_date(args_date: Optional[str], tz: ZoneInfo) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(tz).strftime("%Y-%m-%d")


def target_month(args_month: Optional[str], tz: ZoneInfo) -> str:
    if args_month:
        datetime.strptime(args_month, "%Y-%m")
        return args_month
    return datetime.now(tz).strftime("%Y-%m")


def day_bounds(date_str: str, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    return start, start + timedelta(days=1)


def parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def is_in_day(ts: str, start: datetime, end: datetime) -> bool:
    parsed = parse_timestamp(ts)
    if not parsed:
        return False
    local = parsed.astimezone(start.tzinfo)
    return start <= local < end


def local_time(ts: str, tz: ZoneInfo) -> str:
    parsed = parse_timestamp(ts)
    if not parsed:
        return "??:??"
    return parsed.astimezone(tz).strftime("%H:%M")


def weekday_name(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")


def iso_week(date_str: str) -> Tuple[int, int]:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    cal = d.isocalendar()
    return cal[0], cal[1]


def week_date_range(year: int, week: int) -> Tuple[str, str]:
    """Return (monday, sunday) as YYYY-MM-DD strings for the given ISO week."""
    jan4 = datetime(year, 1, 4).date()
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_week1 + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")
