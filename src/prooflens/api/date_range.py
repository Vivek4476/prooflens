"""Parse ISO-8601 date-range bounds for analytics filtering.

Accepts a date-only string (YYYY-MM-DD, whole-day semantics) or a full
ISO-8601 timestamp (exact instant). Returns a timezone-aware UTC datetime, or
None when no bound is given. Raises ValueError on malformed input so the API
layer can return HTTP 400.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def parse_bound(value: str | None, *, is_end: bool) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    # Date-only (YYYY-MM-DD) -> whole-day semantics.
    if len(v) == 10 and v[4] == "-" and v[7] == "-":
        d = date.fromisoformat(v)  # raises ValueError on a bad date
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        return dt + timedelta(days=1) if is_end else dt
    # Full timestamp -> exact instant; naive input is treated as UTC.
    dt = datetime.fromisoformat(v)  # raises ValueError on malformed input
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
