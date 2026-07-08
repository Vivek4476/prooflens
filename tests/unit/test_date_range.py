"""parse_bound: date-only -> whole-day; full timestamp -> exact instant; UTC."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from prooflens.api.date_range import parse_bound, resolve_range, fill_series


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


UTC_ALIAS = timezone.utc


def _today():
    return datetime.now(UTC_ALIAS).date()


def test_resolve_defaults_to_last_30_days():
    start, end = resolve_range(None, None)
    assert start.date() == _today() - timedelta(days=29)
    assert end.date() == _today() + timedelta(days=1)      # exclusive next-midnight
    assert (end - start).days == 30


def test_resolve_only_start_defaults_end_to_today():
    d = (_today() - timedelta(days=3)).isoformat()
    start, end = resolve_range(d, None)
    assert start.date() == _today() - timedelta(days=3)
    assert end.date() == _today() + timedelta(days=1)


def test_resolve_only_end_defaults_start_30_back():
    d = (_today() - timedelta(days=2)).isoformat()
    start, end = resolve_range(None, d)
    assert end.date() == _today() - timedelta(days=1)      # exclusive of (d+1)
    assert start.date() == (_today() - timedelta(days=2)) - timedelta(days=29)


def test_resolve_same_day_is_valid():
    d = (_today() - timedelta(days=1)).isoformat()
    start, end = resolve_range(d, d)
    assert (end - start).days == 1


def test_resolve_future_start_rejected():
    d = (_today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="start_date is in the future"):
        resolve_range(d, None)


def test_resolve_future_end_rejected():
    d = (_today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="end_date is in the future"):
        resolve_range(None, d)


def test_resolve_start_after_end_rejected():
    s = (_today() - timedelta(days=1)).isoformat()
    e = (_today() - timedelta(days=5)).isoformat()
    with pytest.raises(ValueError, match="start_date must be <= end_date"):
        resolve_range(s, e)


def test_resolve_span_over_400_days_rejected():
    s = (_today() - timedelta(days=500)).isoformat()
    e = _today().isoformat()
    with pytest.raises(ValueError, match="max 400 days"):
        resolve_range(s, e)


class _Row:
    def __init__(self, band, score):
        self.band = band
        self.score = score


def test_fill_series_zero_fills_gaps_in_order():
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 4, tzinfo=UTC)          # covers Jul 1,2,3 (exclusive end)
    by_day = {
        "2026-07-01": [_Row("Clear", 80.0), _Row("Suspect", 10.0)],
        "2026-07-03": [_Row("Doubtful", 50.0)],
    }
    series = fill_series(by_day, start, end)
    assert [b["date"] for b in series] == ["2026-07-01", "2026-07-02", "2026-07-03"]
    assert series[0] == {"date": "2026-07-01", "count": 2, "clear": 1, "doubtful": 0, "suspect": 1, "avg_score": 45.0}
    assert series[1] == {"date": "2026-07-02", "count": 0, "clear": 0, "doubtful": 0, "suspect": 0, "avg_score": 0}
    assert series[2]["count"] == 1 and series[2]["doubtful"] == 1


def test_fill_series_fully_empty_range():
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 3, tzinfo=UTC)          # Jul 1, 2
    series = fill_series({}, start, end)
    assert [b["date"] for b in series] == ["2026-07-01", "2026-07-02"]
    assert all(b["count"] == 0 for b in series)
