from __future__ import annotations

import uuid
from datetime import UTC, datetime

from prooflens.db.models import Result
from prooflens.db.repo import PostgresRepo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.engine.types import CheckOutcome, Verdict
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo() -> InMemoryRepo:
    t = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    return InMemoryRepo([t])


def _verdict() -> Verdict:
    return Verdict(band="Suspect", score=18.0, reason="Reused image", reason_code="recycled",
                   rubric_version="v3",
                   checks=[CheckOutcome(name="uniqueness", available=True, score=5.0,
                                        summary="near-duplicate of 3 prior", metric=None,
                                        data={}, latency_ms=1.0)])


def test_inmemory_persists_copilot_summary():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict(), copilot_summary="Scored Suspect because reused.")
    view = repo.get_result(rid, tenant_id="t1")
    assert view is not None
    assert view.to_dict()["copilot_summary"] == "Scored Suspect because reused."


def test_inmemory_copilot_summary_defaults_none():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict())
    view = repo.get_result(rid, tenant_id="t1")
    assert view.to_dict()["copilot_summary"] is None


def test_postgres_to_view_reads_stored_summary():
    row = Result(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), job_id=None, rep_id=None, opportunity_id=None,
        band="Suspect", score=18, reason="Reused image", reason_code="recycled",
        rubric_version="v3", checks=[], created_at=datetime.now(UTC), source="direct",
        copilot_summary="Scored Suspect because reused.",
    )
    view = PostgresRepo._to_view(row, job=None)
    assert view.to_dict()["copilot_summary"] == "Scored Suspect because reused."
