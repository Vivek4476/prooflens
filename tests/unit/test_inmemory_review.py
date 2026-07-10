"""record_review updates the result, writes an audit entry, and filters."""

from __future__ import annotations

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.engine.types import CheckOutcome, Verdict
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo() -> InMemoryRepo:
    t = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    return InMemoryRepo([t])


def _verdict() -> Verdict:
    return Verdict(
        band="Suspect", score=20.0, reason="Suspect — designed graphic",
        reason_code="designed_graphic", rubric_version="v1",
        checks=[CheckOutcome(name="content", available=True, score=0.0, summary="x",
                             metric=None, data={}, latency_ms=1.0)],
    )


def test_record_review_updates_and_audits():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict())
    view = repo.record_review(rid, "approve", "ok", "Demo Operator", tenant_id="t1")
    assert view is not None
    assert view.review_status == "approve" and view.reviewer == "Demo Operator"
    assert view.reviewed_at is not None
    assert repo.audit_log[-1]["event"] == "review.decision"
    assert repo.audit_log[-1]["detail"]["decision"] == "approve"


def test_record_review_unknown_id_returns_none():
    assert _repo().record_review("nope", "approve", None, "Demo Operator", tenant_id="t1") is None


def test_record_review_wrong_tenant_returns_none():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict())
    assert repo.record_review(rid, "approve", None, "Demo Operator", tenant_id="other") is None


def test_list_results_review_filter():
    repo = _repo()
    a = repo.record_result("t1", None, _verdict())
    repo.record_result("t1", None, _verdict())  # left pending
    repo.record_review(a, "reject", None, "Demo Operator", tenant_id="t1")
    pending, _ = repo.list_results(tenant_id="t1", review="pending")
    rejected, _ = repo.list_results(tenant_id="t1", review="reject")
    assert len(pending) == 1 and pending[0].review_status is None
    assert len(rejected) == 1 and rejected[0].id == a


def test_list_results_filters_by_date_range():
    from datetime import UTC, datetime

    repo = _repo()
    repo.record_result("t1", None, _verdict())
    repo.record_result("t1", None, _verdict())
    repo.results[0].created_at = "2026-07-01T09:00:00+00:00"
    repo.results[1].created_at = "2026-07-08T09:00:00+00:00"

    start = datetime(2026, 7, 5, tzinfo=UTC)
    rows, total = repo.list_results(tenant_id="t1", start=start)
    assert total == 1
    assert rows[0].created_at.startswith("2026-07-08")

    end = datetime(2026, 7, 5, tzinfo=UTC)
    rows, total = repo.list_results(tenant_id="t1", end=end)
    assert total == 1
    assert rows[0].created_at.startswith("2026-07-01")
