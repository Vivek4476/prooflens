"""Pure, DB-free unit tests for scripts/lib/seed_data.py (Analytics v4, Pain 3,
Task 9). No DB, no network — everything here runs offline against the
committed scripts/sample-hierarchy.csv fixture."""

from __future__ import annotations

from datetime import UTC, date
from pathlib import Path
from random import Random

import pytest
from scripts.lib.seed_data import (
    daily_record_count,
    generate_agent_pool,
    generate_seed_plan,
    is_weekend,
    sample_review_decision,
    sample_timestamp,
    sample_verdict,
)

from prooflens.engine.types import Verdict
from prooflens.engine.verdicts import BAND_CLEAR, BAND_DOUBTFUL, BAND_SUSPECT, REASON_TEXT, Reason
from prooflens.service.ids import normalize_id
from prooflens.vision.rubric import RUBRIC_VERSION

HIERARCHY_CSV = Path(__file__).resolve().parents[2] / "scripts" / "sample-hierarchy.csv"


# ---------------------------------------------------------------------------
# generate_agent_pool
# ---------------------------------------------------------------------------


def test_agent_pool_reads_hierarchy_csv_and_normalizes():
    pool = generate_agent_pool(HIERARCHY_CSV)
    assert 150 <= len(pool) <= 300
    assert all(a == normalize_id(a) for a in pool)
    assert all(a is not None for a in pool)


def test_agent_pool_normalization_matches_normalize_id_directly(tmp_path):
    csv_path = tmp_path / "h.csv"
    csv_path.write_text(
        "agent_id,sm,rsm,srsm,zonal_head,branch,city,valid_from\n"
        "  rep-1 ,S,R,SR,Z,B,C,2026-01-01\n"
        "REP-2,S,R,SR,Z,B,C,2026-01-01\n"
        ",S,R,SR,Z,B,C,2026-01-01\n"  # blank agent_id -> dropped
    )
    pool = generate_agent_pool(csv_path)
    assert pool == [normalize_id("  rep-1 "), normalize_id("REP-2")]
    assert pool == ["REP-1", "REP-2"]


# ---------------------------------------------------------------------------
# sample_timestamp — working-hours clustering
# ---------------------------------------------------------------------------


def test_sample_timestamp_is_deterministic_for_same_seed():
    day = date(2026, 3, 2)
    ts1 = sample_timestamp(day, Random(42))
    ts2 = sample_timestamp(day, Random(42))
    assert ts1 == ts2


def test_sample_timestamp_within_working_hours_window():
    day = date(2026, 3, 2)
    rng = Random(7)
    for _ in range(500):
        ts = sample_timestamp(day, rng)
        assert ts.date() == day
        assert 9 <= ts.hour < 19 or (ts.hour == 19 and ts.minute == 0)


def test_sample_timestamp_is_timezone_aware_utc():
    """Result.created_at is DateTime(timezone=True); a naive datetime here
    would let Postgres silently reinterpret the sampled hour in the session
    timezone, drifting the intended ~9am-7pm business hours. Must be tz-aware
    UTC, not naive."""
    day = date(2026, 3, 2)
    ts = sample_timestamp(day, Random(42))
    assert ts.tzinfo is not None
    assert ts.utcoffset().total_seconds() == 0
    assert ts.tzinfo == UTC


def test_sample_timestamp_clusters_around_midday():
    day = date(2026, 3, 2)
    rng = Random(11)
    hours = [sample_timestamp(day, rng).hour + sample_timestamp(day, rng).minute / 60
             for _ in range(2000)]
    midday_band = sum(1 for h in hours if 11 <= h <= 16)
    assert midday_band / len(hours) > 0.5  # bell-shaped, not uniform


# ---------------------------------------------------------------------------
# weekday/weekend bias
# ---------------------------------------------------------------------------


def test_is_weekend():
    assert is_weekend(date(2026, 3, 7)) is True   # Saturday
    assert is_weekend(date(2026, 3, 8)) is True   # Sunday
    assert is_weekend(date(2026, 3, 2)) is False  # Monday


def test_daily_record_count_weekend_materially_lighter_but_nonzero():
    rng = Random(99)
    weekday = date(2026, 3, 2)   # Monday
    weekend = date(2026, 3, 7)   # Saturday
    weekday_counts = [daily_record_count(weekday, (30, 90), rng) for _ in range(500)]
    weekend_counts = [daily_record_count(weekend, (30, 90), rng) for _ in range(500)]

    assert all(c > 0 for c in weekend_counts)  # never zero
    assert min(weekday_counts) > 0
    avg_weekday = sum(weekday_counts) / len(weekday_counts)
    avg_weekend = sum(weekend_counts) / len(weekend_counts)
    assert avg_weekend < avg_weekday * 0.35   # materially lighter
    assert avg_weekend > avg_weekday * 0.05   # but not vanishing


# ---------------------------------------------------------------------------
# sample_verdict — band + reason distribution
# ---------------------------------------------------------------------------


def test_sample_verdict_returns_real_verdict_dataclass():
    v = sample_verdict(Random(1))
    assert isinstance(v, Verdict)
    assert v.rubric_version == RUBRIC_VERSION
    assert v.checks == []


def test_sample_verdict_band_distribution_within_target_ranges():
    rng = Random(2026)
    n = 20_000
    verdicts = [sample_verdict(rng) for _ in range(n)]
    bands = [v.band for v in verdicts]

    suspect_frac = bands.count(BAND_SUSPECT) / n
    doubtful_frac = bands.count(BAND_DOUBTFUL) / n
    clear_frac = bands.count(BAND_CLEAR) / n

    # Target ranges per the brief, with statistical tolerance for sampling noise.
    assert 0.01 <= suspect_frac <= 0.07, suspect_frac
    assert 0.06 <= doubtful_frac <= 0.14, doubtful_frac
    assert clear_frac > 0.80, clear_frac
    assert abs(suspect_frac + doubtful_frac + clear_frac - 1.0) < 1e-9


def test_sample_verdict_reasons_are_real_enum_values_with_matching_text():
    rng = Random(55)
    for _ in range(5000):
        v = sample_verdict(rng)
        reason_code = Reason(v.reason_code)   # raises if not a real enum value
        assert v.reason == REASON_TEXT[reason_code]


def test_sample_verdict_clear_band_always_uses_clear_reason():
    rng = Random(3)
    for _ in range(5000):
        v = sample_verdict(rng)
        if v.band == BAND_CLEAR:
            assert v.reason_code == Reason.CLEAR.value


def test_sample_verdict_score_matches_band_range():
    rng = Random(4)
    for _ in range(5000):
        v = sample_verdict(rng)
        if v.band == BAND_CLEAR:
            assert v.score >= 70.0
        elif v.band == BAND_DOUBTFUL:
            assert 40.0 <= v.score < 70.0
        else:
            assert v.score < 40.0


def test_sample_verdict_scores_are_not_always_boundary_values():
    rng = Random(6)
    scores = {round(sample_verdict(rng).score, 2) for _ in range(500)}
    assert len(scores) > 50  # varied, not pinned to a couple of boundary values


def test_sample_verdict_doubtful_and_suspect_use_plausible_reason_mix():
    rng = Random(8)
    suspect_reasons = []
    doubtful_reasons = []
    for _ in range(20_000):
        v = sample_verdict(rng)
        if v.band == BAND_SUSPECT:
            suspect_reasons.append(v.reason_code)
        elif v.band == BAND_DOUBTFUL:
            doubtful_reasons.append(v.reason_code)

    dominant_suspect = {
        Reason.RECYCLED.value, Reason.SCREEN_RECAPTURE.value,
        Reason.DESIGNED_GRAPHIC.value, Reason.NO_PEOPLE_OR_IRRELEVANT.value,
    }
    dominant_doubtful = {Reason.TOO_BLURRED.value, Reason.NO_CONTENT_ANALYSIS.value}

    assert suspect_reasons and doubtful_reasons
    assert sum(1 for r in suspect_reasons if r in dominant_suspect) / len(suspect_reasons) > 0.6
    assert sum(1 for r in doubtful_reasons if r in dominant_doubtful) / len(doubtful_reasons) > 0.5


# ---------------------------------------------------------------------------
# generate_seed_plan
# ---------------------------------------------------------------------------


def test_generate_seed_plan_is_deterministic_for_same_seed():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan1 = generate_seed_plan(30, (30, 90), pool, Random(123))
    plan2 = generate_seed_plan(30, (30, 90), pool, Random(123))
    assert plan1 == plan2


def test_generate_seed_plan_produces_low_to_mid_thousands_over_75_days():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan = generate_seed_plan(75, (30, 90), pool, Random(2026))
    assert 1500 <= len(plan) <= 7000


def test_generate_seed_plan_rep_ids_all_in_agent_pool():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan = generate_seed_plan(20, (30, 90), pool, Random(5))
    pool_set = set(pool)
    assert all(r.rep_id in pool_set for r in plan)


def test_generate_seed_plan_opportunity_ids_are_unique_and_stable_format():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan = generate_seed_plan(10, (30, 90), pool, Random(9))
    opp_ids = [r.opportunity_id for r in plan]
    assert len(opp_ids) == len(set(opp_ids))
    assert all(o.startswith("OPP-") and len(o) == 10 for o in opp_ids)


def test_generate_seed_plan_weekday_records_exceed_weekend_records():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan = generate_seed_plan(60, (30, 90), pool, Random(2027), start_day=date(2026, 1, 1))
    weekday_count = sum(1 for r in plan if not is_weekend(r.created_at.date()))
    weekend_count = sum(1 for r in plan if is_weekend(r.created_at.date()))
    assert weekend_count > 0
    assert weekday_count > weekend_count


def test_generate_seed_plan_timestamps_within_window():
    pool = generate_agent_pool(HIERARCHY_CSV)
    plan = generate_seed_plan(15, (30, 90), pool, Random(3))
    in_hours = sum(1 for r in plan if 9 <= r.created_at.hour < 19)
    assert in_hours / len(plan) > 0.80


def test_generate_seed_plan_rejects_empty_agent_pool():
    with pytest.raises(ValueError):
        generate_seed_plan(10, (30, 90), [], Random(1))


def test_generate_seed_plan_rejects_nonpositive_days():
    with pytest.raises(ValueError):
        generate_seed_plan(0, (30, 90), ["A1"], Random(1))


# ---------------------------------------------------------------------------
# sample_review_decision — realistic review outcomes for flagged results
# ---------------------------------------------------------------------------


def _verdict(band: str) -> Verdict:
    reason_code = Reason.CLEAR if band == BAND_CLEAR else Reason.RECYCLED
    return Verdict(
        score=10.0, band=band, reason=REASON_TEXT[reason_code],
        reason_code=reason_code.value, checks=[], rubric_version=RUBRIC_VERSION,
    )


def test_sample_review_decision_is_deterministic_for_same_seed():
    v = _verdict(BAND_SUSPECT)
    d1 = sample_review_decision(v, Random(42))
    d2 = sample_review_decision(v, Random(42))
    assert d1 == d2


def test_sample_review_decision_clear_band_never_reviewed():
    rng = Random(11)
    v = _verdict(BAND_CLEAR)
    for _ in range(2000):
        assert sample_review_decision(v, rng) is None


def test_sample_review_decision_returns_only_valid_outcomes():
    rng = Random(5)
    valid = {"reject", "approve", "false_positive", "escalate", None}
    for band in (BAND_SUSPECT, BAND_DOUBTFUL):
        v = _verdict(band)
        for _ in range(2000):
            assert sample_review_decision(v, rng) in valid


def test_sample_review_decision_distribution_realistic():
    rng = Random(2026)
    n = 20_000
    outcomes = [sample_review_decision(_verdict(BAND_SUSPECT), rng) for _ in range(n)]
    reviewed = [o for o in outcomes if o is not None]
    reviewed_frac = len(reviewed) / n
    # ~60% of flagged items get reviewed.
    assert 0.45 <= reviewed_frac <= 0.75, reviewed_frac

    reject_frac = reviewed.count("reject") / len(reviewed)
    approve_frac = reviewed.count("approve") / len(reviewed)
    fp_frac = reviewed.count("false_positive") / len(reviewed)
    escalate_frac = reviewed.count("escalate") / len(reviewed)

    # Mostly "reject" (flag was right) so precision lands ~78-85%.
    assert 0.70 <= reject_frac <= 0.92, reject_frac
    assert escalate_frac < 0.15, escalate_frac
    assert (approve_frac + fp_frac) > 0.0
    assert abs(reject_frac + approve_frac + fp_frac + escalate_frac - 1.0) < 1e-9


def test_sample_review_decision_precision_lands_in_target_band():
    rng = Random(777)
    n = 20_000
    outcomes = [sample_review_decision(_verdict(BAND_DOUBTFUL), rng) for _ in range(n)]
    confirmed = sum(1 for o in outcomes if o == "reject")
    overturned = sum(1 for o in outcomes if o in ("approve", "false_positive"))
    reviewed = confirmed + overturned
    precision_pct = 100.0 * confirmed / reviewed
    assert 78.0 <= precision_pct <= 85.0, precision_pct


# ---------------------------------------------------------------------------
# processing_ms enrichment (system-health median is non-zero)
# ---------------------------------------------------------------------------

def test_sample_processing_checks_have_realistic_latencies():
    from prooflens.service.repo import processing_ms
    from prooflens.engine.types import Verdict
    from scripts.lib.seed_data import sample_processing_checks
    from prooflens.engine.verdicts import BAND_CLEAR
    rng = Random(7)
    checks = sample_processing_checks(rng, BAND_CLEAR)
    names = {c.name for c in checks}
    assert {"exif", "blur", "uniqueness", "recapture", "content"} <= names
    v = Verdict(score=90.0, band=BAND_CLEAR, reason="", reason_code="clear",
                checks=checks, rubric_version="v3")
    assert processing_ms(v) > 0  # non-zero total wall-clock


def test_generate_seed_plan_records_have_nonzero_processing_ms():
    from prooflens.service.repo import processing_ms
    from statistics import median
    pool = ["AGENT-1", "AGENT-2"]
    plan = generate_seed_plan(days=30, records_per_day_range=(3, 8),
                              agent_pool=pool, rng=Random(7))
    procs = [processing_ms(r.verdict) for r in plan]
    assert all(p >= 0 for p in procs)
    assert median(procs) > 50  # a realistic median, not 0 ms
