"""results.source: stored provenance ("direct" | "webhook" | "seed").

Covers both repo implementations:
- InMemoryRepo: full round-trip through record_result -> ResultView.
- PostgresRepo._to_view: exercised directly against Result ORM instances (no
  live DB needed — _to_view is a pure static mapper), proving it reads the
  STORED column and still derives correctly for a legacy row with no stored
  source (simulating a pre-migration row the backfill might have missed).
"""

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
    return Verdict(
        band="Suspect", score=20.0, reason="Suspect — designed graphic",
        reason_code="designed_graphic", rubric_version="v1",
        checks=[CheckOutcome(name="content", available=True, score=0.0, summary="x",
                             metric=None, data={}, latency_ms=1.0)],
    )


# --- InMemoryRepo ---

def test_inmemory_direct_result_has_direct_source():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict())
    view = repo.get_result(rid)
    assert view is not None
    assert view.source == "direct"


def test_inmemory_webhook_result_has_webhook_source():
    repo = _repo()
    rid = repo.record_result("t1", "job-123", _verdict())
    view = repo.get_result(rid)
    assert view is not None
    assert view.source == "webhook"


def test_inmemory_seed_result_round_trips_as_seed():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict(), source="seed")
    view = repo.get_result(rid)
    assert view is not None
    assert view.source == "seed"


def test_inmemory_seed_override_wins_even_with_job_id():
    # Explicit source overrides the job_id-based derivation entirely.
    repo = _repo()
    rid = repo.record_result("t1", "job-456", _verdict(), source="seed")
    view = repo.get_result(rid)
    assert view is not None
    assert view.source == "seed"


# --- PostgresRepo._to_view (pure mapper, no live DB required) ---

def _result_row(**overrides) -> Result:
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        job_id=None,
        rep_id=None,
        opportunity_id=None,
        band="Suspect",
        score=20,
        reason="Suspect — designed graphic",
        reason_code="designed_graphic",
        rubric_version="v1",
        checks=[],
        created_at=datetime.now(UTC),
        source="direct",
        review_status=None,
        review_note=None,
        reviewed_at=None,
        reviewer=None,
    )
    defaults.update(overrides)
    return Result(**defaults)


def test_postgres_to_view_uses_stored_seed_source():
    row = _result_row(source="seed")
    view = PostgresRepo._to_view(row, job=None)
    assert view.source == "seed"


def test_postgres_to_view_uses_stored_webhook_source_even_without_job_id_link():
    # Stored column is authoritative even if the job row itself isn't loaded.
    row = _result_row(source="webhook", job_id=uuid.uuid4())
    view = PostgresRepo._to_view(row, job=None)
    assert view.source == "webhook"


def test_postgres_to_view_falls_back_to_derivation_for_legacy_null_source():
    # Simulates a row from before the migration's backfill ran (defence in
    # depth only — the migration itself backfills every existing row).
    row = _result_row(source=None, job_id=uuid.uuid4())
    view = PostgresRepo._to_view(row, job=None)
    assert view.source == "webhook"

    row_direct = _result_row(source=None, job_id=None)
    view_direct = PostgresRepo._to_view(row_direct, job=None)
    assert view_direct.source == "direct"
