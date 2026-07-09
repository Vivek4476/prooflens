# tests/unit/test_analytics_agg.py
from __future__ import annotations

from datetime import UTC, date, datetime

from prooflens.api.analytics import aggregate_range, build_buckets, flag_precision, system_health
from prooflens.service.views import ResultView


def _r(day: date, band="Clear", score=90.0, reason=None, rep_id=None, review_status=None,
       processing_ms=0.0):
    # reason_code defaults to band.lower() ("clear"/"doubtful"/"suspect") when
    # not given explicitly, so items built with only (day, band, score) get a
    # reason_code consistent with their band.
    reason_code = reason if reason is not None else band.lower()
    return ResultView(
        id="x", created_at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC).isoformat(),
        tenant_id="t1", band=band, score=score, reason="r", reason_code=reason_code,
        rubric_version="v3", rep_id=rep_id, review_status=review_status,
        processing_ms=processing_ms,
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


def test_incomplete_flag_uses_injected_today_not_wall_clock():
    # Injected `today` is deliberately far from wall-clock so this can never
    # pass by accident of when the suite happens to run.
    injected_today = date(2030, 3, 15)
    start, end = _dt(date(2030, 3, 13)), _dt(date(2030, 3, 17))  # Mar 13,14,15,16
    items = [_r(date(2030, 3, 13)), _r(date(2030, 3, 15))]
    b = build_buckets(items, start, end, "daily", today=injected_today)
    by_label = {x["bucket_label"]: x for x in b}
    assert by_label["2030-03-15"]["incomplete"] is True
    assert by_label["2030-03-13"]["incomplete"] is False
    assert by_label["2030-03-14"]["incomplete"] is False
    # Buckets after today's bucket are also not "incomplete" under the
    # half-open [bucket.start, bucket.end) containment rule.
    assert by_label["2030-03-16"]["incomplete"] is False


def test_aggregate_range_passes_injected_today_through_to_buckets():
    injected_today = date(2030, 3, 15)
    start, end = _dt(date(2030, 3, 13)), _dt(date(2030, 3, 17))
    items = [_r(date(2030, 3, 13)), _r(date(2030, 3, 15))]
    out = aggregate_range(items, [], [], start=start, end=end, bucket="daily",
                          group_by="none", today=injected_today)
    by_label = {x["bucket_label"]: x for x in out["series"]}
    assert by_label["2030-03-15"]["incomplete"] is True
    assert by_label["2030-03-13"]["incomplete"] is False
    assert out["incomplete"] is True


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


def test_weekly_bucket_end_clamped_to_range_end_when_not_multiple_of_7():
    # Range Jun 1–Jun 10 (10 days): NOT a multiple of 7.
    # Without the fix, the 2nd bucket reports end=2026-06-14 (4 days past range end).
    # With the fix, the 2nd bucket reports end=2026-06-09 (range end minus 1).
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 11))  # 10 days
    items = [_r(date(2026, 6, 2), "Clear", 80), _r(date(2026, 6, 9), "Suspect", 10)]
    b = build_buckets(items, start, end, "weekly")
    assert len(b) == 2, f"Expected 2 buckets, got {len(b)}"
    # Week 1: Jun 1–7 (full week)
    assert b[0]["bucket_label"] == "Week 1"
    assert b[0]["start"] == "2026-06-01"
    assert b[0]["end"] == "2026-06-07", f"Week 1 end should be 2026-06-07, got {b[0]['end']}"
    assert b[0]["total"] == 1 and b[0]["clear"] == 1
    # Week 2: Jun 8–10 (partial, clamped to range end)
    assert b[1]["bucket_label"] == "Week 2"
    assert b[1]["start"] == "2026-06-08"
    # CRITICAL: end must NOT exceed range_end (2026-06-10)
    assert (
        b[1]["end"] == "2026-06-10"
    ), f"Week 2 end should be clamped to 2026-06-10, got {b[1]['end']}"
    assert b[1]["total"] == 1 and b[1]["suspect"] == 1


# ---------------------------------------------------------------------------
# flag_precision
# ---------------------------------------------------------------------------


def test_flag_precision_worked_example_from_spec():
    day = date(2026, 6, 1)
    items = [
        _r(day, "Suspect", 10, review_status="reject"),
        _r(day, "Suspect", 10, review_status="reject"),
        _r(day, "Doubtful", 50, review_status="reject"),
        _r(day, "Suspect", 10, review_status="approve"),
        _r(day, "Doubtful", 50, review_status="false_positive"),
    ]
    out = flag_precision(items)
    assert out == {
        "reviewed": 5, "confirmed": 3, "overturned": 2, "precision_pct": 60.0,
    }


def test_flag_precision_excludes_escalate_and_pending():
    day = date(2026, 6, 1)
    items = [
        _r(day, "Suspect", 10, review_status="reject"),
        _r(day, "Suspect", 10, review_status="escalate"),
        _r(day, "Doubtful", 50, review_status=None),
    ]
    out = flag_precision(items)
    assert out == {
        "reviewed": 1, "confirmed": 1, "overturned": 0, "precision_pct": 100.0,
    }


def test_flag_precision_excludes_clear_even_if_reviewed():
    day = date(2026, 6, 1)
    items = [
        _r(day, "Clear", 90, review_status="reject"),
        _r(day, "Clear", 90, review_status="approve"),
        _r(day, "Suspect", 10, review_status="reject"),
    ]
    out = flag_precision(items)
    assert out == {
        "reviewed": 1, "confirmed": 1, "overturned": 0, "precision_pct": 100.0,
    }


def test_flag_precision_reviewed_zero_gives_null_precision():
    day = date(2026, 6, 1)
    items = [
        _r(day, "Suspect", 10, review_status=None),
        _r(day, "Doubtful", 50, review_status="escalate"),
        _r(day, "Clear", 90, review_status="reject"),
    ]
    out = flag_precision(items)
    assert out == {
        "reviewed": 0, "confirmed": 0, "overturned": 0, "precision_pct": None,
    }


def test_flag_precision_overturned_counts_both_approve_and_false_positive():
    day = date(2026, 6, 1)
    items = [
        _r(day, "Suspect", 10, review_status="approve"),
        _r(day, "Suspect", 10, review_status="false_positive"),
    ]
    out = flag_precision(items)
    assert out == {
        "reviewed": 2, "confirmed": 0, "overturned": 2, "precision_pct": 0.0,
    }


def test_flag_precision_empty_items():
    out = flag_precision([])
    assert out == {
        "reviewed": 0, "confirmed": 0, "overturned": 0, "precision_pct": None,
    }


def test_aggregate_range_includes_flag_precision_block():
    start, end = _dt(date(2026, 6, 8)), _dt(date(2026, 6, 15))
    items = [
        _r(date(2026, 6, 10), "Suspect", 10, review_status="reject"),
        _r(date(2026, 6, 11), "Suspect", 10, review_status="approve"),
        _r(date(2026, 6, 12), "Clear", 90, review_status="reject"),
    ]
    out = aggregate_range(items, [], [], start=start, end=end, bucket="daily",
                          group_by="none", today=date(2026, 6, 20))
    assert out["flag_precision"] == {
        "reviewed": 2, "confirmed": 1, "overturned": 1, "precision_pct": 50.0,
    }


# --- system_health (v4 Pain 9) ----------------------------------------------


def test_system_health_scored_without_content_pct_counts_only_no_content_analysis():
    day = date(2026, 6, 1)
    # 2 of 10 scored without a content/vision check (fail-open); the other 8
    # have unrelated reason codes and must NOT be counted.
    items = (
        [_r(day, "Doubtful", 50, reason="no_content_analysis") for _ in range(2)]
        + [_r(day, "Clear", 90, reason="clear") for _ in range(3)]
        + [_r(day, "Suspect", 10, reason="recycled") for _ in range(2)]
        + [_r(day, "Doubtful", 50, reason="too_blurred") for _ in range(3)]
    )
    out = system_health(items)
    assert out["scored_without_content_pct"] == 20.0


def test_system_health_median_processing_ms_odd_count():
    day = date(2026, 6, 1)
    items = [_r(day, processing_ms=ms) for ms in (100.0, 300.0, 200.0)]
    out = system_health(items)
    assert out["median_processing_ms"] == 200.0


def test_system_health_median_processing_ms_even_count():
    day = date(2026, 6, 1)
    items = [_r(day, processing_ms=ms) for ms in (100.0, 200.0, 300.0, 400.0)]
    out = system_health(items)
    assert out["median_processing_ms"] == 250.0


def test_system_health_empty_items_gives_null_for_both_fields():
    out = system_health([])
    assert out == {"scored_without_content_pct": None, "median_processing_ms": None}


def test_aggregate_range_includes_system_health_block():
    start, end = _dt(date(2026, 6, 8)), _dt(date(2026, 6, 15))
    items = [
        _r(date(2026, 6, 10), "Doubtful", 50, reason="no_content_analysis", processing_ms=100.0),
        _r(date(2026, 6, 11), "Clear", 90, reason="clear", processing_ms=300.0),
    ]
    out = aggregate_range(items, [], [], start=start, end=end, bucket="daily",
                          group_by="none", today=date(2026, 6, 20))
    assert out["system_health"] == {
        "scored_without_content_pct": 50.0, "median_processing_ms": 200.0,
    }
