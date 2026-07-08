"""parse_bound: date-only -> whole-day; full timestamp -> exact instant; UTC."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from prooflens.api.date_range import parse_bound

UTC = timezone.utc


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
