# tests/unit/test_analytics_agg.py
from __future__ import annotations

from datetime import UTC, date, datetime

from prooflens.api.analytics import aggregate_range, build_buckets
from prooflens.service.views import ResultView


def _r(day: date, band="Clear", score=90.0, reason=None, rep_id=None):
    # reason_code defaults to band.lower() ("clear"/"doubtful"/"suspect") when
    # not given explicitly, so items built with only (day, band, score) get a
    # reason_code consistent with their band.
    reason_code = reason if reason is not None else band.lower()
    return ResultView(
        id="x", created_at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC).isoformat(),
        tenant_id="t1", band=band, score=score, reason="r", reason_code=reason_code,
        rubric_version="v3", rep_id=rep_id,
    )


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def test_daily_buckets_count_and_labels():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 4))   # Jun 1,2,3
    items = [_r(date(2026, 6, 1), "Clear", 80), _r(date(2026, 6, 1), "Suspect", 10),
             _r(date(2026, 6, 3), "Doubtful", 50)]
    b = build_buckets(items, start, end, "daily")
    assert [x["bucket_label"] for x in b] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert b[0]["total"] == 2 and b[0]["clear"] == 1 and b[0]["suspect"] == 1
    assert b[0]["avg_score"] == 45.0
    assert b[1]["total"] == 0
    assert b[2]["doubtful"] == 1


def test_weekly_buckets_anchored_to_range_start():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 15))  # 14 days -> 2 full weeks
    items = [_r(date(2026, 6, 2)), _r(date(2026, 6, 9))]        # week1, week2
    b = build_buckets(items, start, end, "weekly")
    assert [x["bucket_label"] for x in b] == ["Week 1", "Week 2"]
    assert b[0]["total"] == 1 and b[1]["total"] == 1
    assert b[0]["start"] == "2026-06-01" and b[0]["end"] == "2026-06-07"


def test_monthly_buckets_are_calendar_months():
    start, end = _dt(date(2026, 5, 15)), _dt(date(2026, 7, 2))
    items = [_r(date(2026, 5, 20)), _r(date(2026, 6, 10)), _r(date(2026, 7, 1))]
    b = build_buckets(items, start, end, "monthly")
    assert [x["bucket_label"] for x in b] == ["2026-05", "2026-06", "2026-07"]
    assert all(x["total"] == 1 for x in b)


def test_incomplete_flag_on_todays_bucket():
    today = datetime.now(UTC).date()
    start, end = _dt(today), _dt(date(today.year, today.month, today.day))
    # a 1-day range ending after today is not valid via resolve_range; test build_buckets directly
    from datetime import timedelta
    start = _dt(today - timedelta(days=1))
    end = _dt(today + timedelta(days=1))            # covers yesterday + today
    b = build_buckets([_r(today)], start, end, "daily")
    assert b[-1]["bucket_label"] == today.isoformat()
    assert b[-1]["incomplete"] is True
    assert b[0]["incomplete"] is False              # yesterday is complete


def test_aggregate_previous_period_window_and_delta():
    # Range Jun 8..Jun 14 (7 days). Previous equal-length period = Jun 1..Jun 7.
    start, end = _dt(date(2026, 6, 8)), _dt(date(2026, 6, 15))
    items = [_r(date(2026, 6, 10), "Suspect", 10), _r(date(2026, 6, 11), "Clear", 90)]
    prev = [_r(date(2026, 6, 2), "Suspect", 20)]
    out = aggregate_range(items, prev, [], start=start, end=end, bucket="daily",
                          group_by="none", today=date(2026, 6, 20))
    assert out["period"] == {"from": "2026-06-08", "to": "2026-06-14"}
    assert out["previous_period"] == {"from": "2026-06-01", "to": "2026-06-07"}
    assert out["previous"]["total"] == 1 and out["previous"]["suspect"] == 1
    assert out["groups"] == []
    assert out["reason_counts"]["suspect"] == 1 and out["reason_counts"]["clear"] == 1


def test_aggregate_group_by_includes_unmapped():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 8))
    rows = [{"agent_id": "A1", "sm": None, "rsm": None, "srsm": None,
             "zonal_head": None, "branch": "North", "city": None,
             "valid_from": date(2026, 1, 1)}]
    items = [
        _r(date(2026, 6, 2), "Suspect", 10, "recycled", rep_id="A1"),  # North
        _r(date(2026, 6, 3), "Clear", 90, "clear", rep_id="A1"),       # North
        _r(date(2026, 6, 4), "Suspect", 10, "recycled", rep_id="A2"),  # Unmapped
    ]
    out = aggregate_range(items, [], rows, start=start, end=end, bucket="daily",
                          group_by="branch", today=date(2026, 6, 20))
    groups = {g["node"]: g for g in out["groups"]}
    assert set(groups) == {"North", "Unmapped"}
    assert groups["North"]["total"] == 2 and groups["North"]["suspect"] == 1
    assert groups["North"]["suspect_rate"] == 0.5
    assert groups["Unmapped"]["total"] == 1 and groups["Unmapped"]["suspect"] == 1
    assert round(groups["North"]["share"] + groups["Unmapped"]["share"], 3) == 1.0
