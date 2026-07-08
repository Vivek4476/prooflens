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
