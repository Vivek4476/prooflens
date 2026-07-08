"""parse_bound: date-only -> whole-day; full timestamp -> exact instant; UTC."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prooflens.api.date_range import parse_bound


def test_none_and_empty_return_none():
    assert parse_bound(None, is_end=False) is None
    assert parse_bound("", is_end=True) is None


def test_date_only_start_is_midnight_utc():
    assert parse_bound("2026-07-08", is_end=False) == datetime(2026, 7, 8, tzinfo=UTC)


def test_date_only_end_adds_one_day():
    # end is inclusive of the whole day -> next midnight
    assert parse_bound("2026-07-08", is_end=True) == datetime(2026, 7, 9, tzinfo=UTC)


def test_full_timestamp_with_offset_is_exact_instant():
    assert parse_bound("2026-07-08T14:30:00+00:00", is_end=False) == datetime(
        2026, 7, 8, 14, 30, tzinfo=UTC
    )


def test_naive_timestamp_is_treated_as_utc():
    assert parse_bound("2026-07-08T14:30:00", is_end=False) == datetime(
        2026, 7, 8, 14, 30, tzinfo=UTC
    )


def test_malformed_raises_valueerror():
    with pytest.raises(ValueError):
        parse_bound("not-a-date", is_end=False)


def test_offset_aware_timestamp_is_normalized_to_utc():
    result = parse_bound("2026-07-08T10:00:00-05:00", is_end=False)
    assert result == datetime(2026, 7, 8, 15, 0, tzinfo=UTC)
    assert result.tzinfo == UTC
    assert result.utcoffset() == timedelta(0)


def test_basic_format_date_is_not_treated_as_date_only():
    # "20260708" has no dashes, so it must NOT match the strict YYYY-MM-DD
    # date-only regex and should fall through to timestamp parsing instead.
    # datetime.fromisoformat("20260708") parses this basic-format ISO string
    # as a naive datetime at midnight, which is then treated as UTC.
    result = parse_bound("20260708", is_end=False)
    assert result == datetime(2026, 7, 8, tzinfo=UTC)
