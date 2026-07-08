"""Parse ISO-8601 date-range bounds for analytics filtering.

Accepts a date-only string (YYYY-MM-DD, whole-day semantics) or a full
ISO-8601 timestamp (exact instant). Returns a timezone-aware UTC datetime, or
None when no bound is given. Raises ValueError on malformed input so the API
layer can return HTTP 400.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

_DATE_ONLY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_bound(value: str | None, *, is_end: bool) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    # Date-only (YYYY-MM-DD) -> whole-day semantics.
    if _DATE_ONLY_RE.fullmatch(v):
        d = date.fromisoformat(v)  # raises ValueError on a bad date
        dt = datetime(d.year, d.month, d.day, tzinfo=UTC)
        return dt + timedelta(days=1) if is_end else dt
    # Full timestamp -> exact instant; naive input is treated as UTC.
    dt = datetime.fromisoformat(v)  # raises ValueError on malformed input
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    # Normalize offset-aware inputs (and the now-UTC-tagged naive ones) so the
    # returned tzinfo is always exactly UTC.
    return dt.astimezone(UTC)


_DEFAULT_DAYS = 30
_MAX_SPAN_DAYS = 400


def _bound_day(value: str | None) -> date | None:
    dt = parse_bound(value, is_end=False)   # raw day start (or instant); we take the date
    return dt.date() if dt is not None else None


def resolve_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    """Resolve optional ISO date bounds into a bounded half-open [start, end) UTC range.

    Defaults to the last 30 days when a bound is omitted. Day-granular and UTC.
    Raises ValueError (-> HTTP 400) on a future date, start>end, or span > 400 days.
    """
    today = datetime.now(UTC).date()
    start_day = _bound_day(start_date)
    end_day = _bound_day(end_date)

    if start_day is None and end_day is None:
        end_day = today
        start_day = today - timedelta(days=_DEFAULT_DAYS - 1)
    elif start_day is None:
        start_day = end_day - timedelta(days=_DEFAULT_DAYS - 1)
    elif end_day is None:
        end_day = today

    if start_date is not None and start_day > today:
        raise ValueError("start_date is in the future")
    if end_date is not None and end_day > today:
        raise ValueError("end_date is in the future")
    if start_day > end_day:
        raise ValueError("start_date must be <= end_date")
    if (end_day - start_day).days + 1 > _MAX_SPAN_DAYS:
        raise ValueError(f"date range too large (max {_MAX_SPAN_DAYS} days)")

    start = datetime(start_day.year, start_day.month, start_day.day, tzinfo=UTC)
    end_next = end_day + timedelta(days=1)
    end = datetime(end_next.year, end_next.month, end_next.day, tzinfo=UTC)
    return start, end
