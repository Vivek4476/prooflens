"""POST /v1/bulk-score + GET /v1/bulk-score/{job_id} — bulk photo scoring
(Phase 1). Fully offline: InMemoryRepo + FakeLSQClient + stub vision backend.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.bulk import get_lsq_client
from prooflens.api.deps import get_repo, get_repo_factory
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.lsq.fake import BAD_FETCH_MARKER, FakeLSQClient
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _tenant() -> TenantView:
    return TenantView(
        id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig(),
        vision_backend="stub",
    )


@pytest.fixture
def repo() -> InMemoryRepo:
    return InMemoryRepo([_tenant()])


@pytest.fixture
def lsq() -> FakeLSQClient:
    return FakeLSQClient()


@pytest.fixture(autouse=True)
def _reset_registry():
    # The bulk registry is a process-wide singleton; reset it around every test
    # so jobs from one test can't pollute another's active_count/eviction state.
    from prooflens.service import bulk as bulk_mod

    bulk_mod.registry._jobs.clear()
    yield
    bulk_mod.registry._jobs.clear()


@pytest.fixture
def client(repo, lsq) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    # Background rows each call repo_factory(); reuse the same InMemoryRepo
    # (safe — it has no per-call session state) with a no-op close.
    app.dependency_overrides[get_repo_factory] = lambda: (lambda: (repo, lambda: None))
    app.dependency_overrides[get_lsq_client] = lambda: lsq

    from prooflens.api.auth import require_tenant

    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
    return TestClient(app, raise_server_exceptions=False)


def _poll_until_done(client, job_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/v1/bulk-score/{job_id}").json()
        if body["status"] == "done":
            return body
        time.sleep(0.02)
    raise AssertionError("bulk job did not complete in time")


def test_bulk_batch_scores_attributes_and_fails_open_on_bad_row(client, repo):
    rows = [
        {"image_url": "https://lsq.example/photo1.jpg", "rep_id": "A1", "opportunity_id": "OPP1"},
        {"image_url": "https://lsq.example/photo2.jpg", "rep_id": "A2", "opportunity_id": "OPP2"},
        {"image_url": f"https://lsq.example/{BAD_FETCH_MARKER}.jpg", "rep_id": "A3",
         "opportunity_id": "OPP3"},
    ]
    r = client.post("/v1/bulk-score", json={"rows": rows, "label": "test batch"})
    assert r.status_code == 200
    body = r.json()
    job_id = body["job_id"]
    assert body["total"] == 3

    final = _poll_until_done(client, job_id)
    assert final["status"] == "done"
    assert final["processed"] == 3
    assert final["total"] == 3
    assert len(final["results"]) == 3

    ok_rows = [row for row in final["results"] if row["error"] is None]
    err_rows = [row for row in final["results"] if row["error"] is not None]
    assert len(ok_rows) == 2
    assert len(err_rows) == 1
    assert err_rows[0]["image_url"].endswith(f"{BAD_FETCH_MARKER}.jpg")
    assert err_rows[0]["band"] is None and err_rows[0]["score"] is None

    for row in ok_rows:
        assert row["band"] is not None
        assert row["score"] is not None
        assert row["reason_code"] is not None
        assert row["result_id"] is not None

    # Persisted as normal Result rows with source="bulk" + attribution.
    persisted = {r.rep_id: r for r in repo.results}
    assert persisted["A1"].source == "bulk"
    assert persisted["A1"].opportunity_id == "OPP1"
    assert persisted["A2"].source == "bulk"
    assert persisted["A2"].opportunity_id == "OPP2"
    assert "A3" not in persisted  # the bad-fetch row never reached record_result
    assert len(repo.results) == 2


def test_get_bulk_score_reflects_progress_before_done(client):
    rows = [{"image_url": "https://lsq.example/p.jpg", "rep_id": None, "opportunity_id": None}]
    r = client.post("/v1/bulk-score", json={"rows": rows})
    job_id = r.json()["job_id"]

    first = client.get(f"/v1/bulk-score/{job_id}").json()
    assert first["status"] in ("queued", "running", "done")
    assert first["total"] == 1
    assert 0 <= first["processed"] <= 1

    final = _poll_until_done(client, job_id)
    assert final["processed"] == 1
    assert final["results"][0]["error"] is None


def test_get_unknown_bulk_job_404(client):
    r = client.get("/v1/bulk-score/does-not-exist")
    assert r.status_code == 404


def test_bulk_score_rejects_oversized_batch(client):
    # A raw caller can't ingest an unbounded row list (OOM guard) — over the
    # hard cap is a 422, not an accepted (and memory-resident) job.
    from prooflens.api.bulk import MAX_BULK_ROWS

    rows = [{"image_url": f"https://lsq.example/p{i}.jpg"} for i in range(MAX_BULK_ROWS + 1)]
    r = client.post("/v1/bulk-score", json={"rows": rows})
    assert r.status_code == 422


def test_bulk_score_rejects_empty_batch(client):
    r = client.post("/v1/bulk-score", json={"rows": []})
    assert r.status_code == 422


def test_bulk_score_rejects_when_too_many_inflight(client):
    # A caller can't spawn unbounded background jobs: at the in-flight cap the
    # endpoint returns 429 instead of starting another fan-out.
    from prooflens.service.bulk import MAX_INFLIGHT_JOBS, registry

    # Jobs created but never run stay "queued" (== in-flight).
    created = [registry.create(total=1) for _ in range(MAX_INFLIGHT_JOBS)]
    try:
        assert registry.active_count() >= MAX_INFLIGHT_JOBS
        r = client.post("/v1/bulk-score", json={"rows": [{"image_url": "https://x/p.jpg"}]})
        assert r.status_code == 429
    finally:
        for j in created:
            registry._jobs.pop(j.id, None)


def test_bulk_registry_eviction_never_drops_in_flight_job():
    # A still-running job must survive eviction — dropping it would 404 a live
    # job the operator is polling. Only done jobs are evicted.
    from prooflens.service.bulk import MAX_RETAINED_JOBS, BulkJobRegistry

    reg = BulkJobRegistry()
    running = reg.create(total=1)
    running.status = "running"  # oldest, but in-flight
    for _ in range(MAX_RETAINED_JOBS + 5):
        done = reg.create(total=1)
        done.status = "done"
    # The running job (oldest) is retained; done jobs were evicted instead.
    assert reg.get(running.id) is not None
    assert len(reg._jobs) <= MAX_RETAINED_JOBS


def test_bulk_registry_active_count_ignores_done():
    from prooflens.service.bulk import BulkJobRegistry

    reg = BulkJobRegistry()
    a = reg.create(total=1)
    b = reg.create(total=1)
    a.status = "done"
    b.status = "running"
    assert reg.active_count() == 1  # only the running one counts


def test_bulk_registry_evicts_oldest_over_cap():
    # The in-memory registry can't grow without bound: once over the retention
    # cap, the oldest job is evicted (returns 404), newest stay resolvable.
    from prooflens.service.bulk import MAX_RETAINED_JOBS, BulkJobRegistry

    reg = BulkJobRegistry()
    first = reg.create(total=1)
    first.status = "done"
    for _ in range(MAX_RETAINED_JOBS):
        j = reg.create(total=1)
        j.status = "done"  # only done jobs are eligible for eviction
    assert reg.get(first.id) is None  # oldest done job evicted
    # The cap holds: never more than MAX_RETAINED_JOBS retained.
    assert len(reg._jobs) == MAX_RETAINED_JOBS


def test_bulk_score_unknown_tenant_row_field_shape(client):
    # Response shape sanity: exact keys per row, even for a null rep/opportunity.
    rows = [{"image_url": "https://lsq.example/p.jpg"}]
    r = client.post("/v1/bulk-score", json={"rows": rows})
    job_id = r.json()["job_id"]
    final = _poll_until_done(client, job_id)
    row = final["results"][0]
    assert set(row.keys()) == {
        "image_url", "rep_id", "opportunity_id", "band", "score",
        "reason_code", "result_id", "error",
    }
    assert row["rep_id"] is None and row["opportunity_id"] is None
