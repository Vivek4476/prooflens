"""End-to-end (offline): signed webhook -> queue -> worker -> FakeLSQ write-back.

Uses the InMemoryRepo + FakeLSQClient + stub backend, so no database, no network
and no paid vision call. Exercises the exact Phase 2 ACCEPT criteria.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app, get_repo
from prooflens.api.security import SIGNATURE_HEADER, sign
from prooflens.config import get_settings
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.lsq import FakeLSQClient
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView
from prooflens.worker import run_once
from tests.helpers import IMAGES_DIR

SECRET = "webhook-s3cr3t"
FIELD_MAP = {"band": "F_BAND", "score": "F_SCORE", "reason": "F_REASON"}


def _tenant(vision_backend: str = "stub") -> TenantView:
    return TenantView(
        id="tenant-1", slug="dev", webhook_secret=SECRET,
        field_map=FIELD_MAP, scoring=ScoringConfig(), vision_backend=vision_backend,
    )


def _run_one_job(vision_backend: str):
    """Mirror the file's e2e wiring (InMemoryRepo + FakeLSQClient + real app) to
    drive exactly one job through the webhook -> worker path, for a tenant
    configured to `vision_backend`."""
    repo = InMemoryRepo([_tenant(vision_backend)])
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    client = TestClient(app)
    _post(client)
    lsq = FakeLSQClient()
    assert run_once(repo, lsq, get_settings()) == 1
    return repo.results[-1]


@pytest.fixture
def repo() -> InMemoryRepo:
    return InMemoryRepo([_tenant()])


@pytest.fixture
def client(repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app)


def _post(client, *, event_id="evt-1", image="meeting.jpg", secret=SECRET):
    b64 = base64.b64encode((IMAGES_DIR / image).read_bytes()).decode()
    payload = {
        "event_id": event_id,
        "opportunity_id": "opp-9",
        "rep_id": "rep-1",
        "image_base64": b64,
    }
    body = json.dumps(payload).encode()
    headers = {SIGNATURE_HEADER: sign(secret, body), "content-type": "application/json"}
    return client.post("/v1/webhooks/lsq/dev", content=body, headers=headers)


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_bad_signature_rejected(client):
    b64 = base64.b64encode((IMAGES_DIR / "meeting.jpg").read_bytes()).decode()
    body = json.dumps({"event_id": "e", "opportunity_id": "o", "image_base64": b64}).encode()
    r = client.post("/v1/webhooks/lsq/dev", content=body,
                    headers={SIGNATURE_HEADER: "deadbeef", "content-type": "application/json"})
    assert r.status_code == 401


def test_unknown_tenant_404(client):
    r = client.post("/v1/webhooks/lsq/nope", content=b"{}", headers={SIGNATURE_HEADER: "x"})
    assert r.status_code == 404


def test_end_to_end_writeback_in_order(client, repo):
    # 1. signed webhook -> accepted, enqueued
    r = _post(client)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    job_id = r.json()["job_id"]

    # 2. worker drains -> one job processed
    lsq = FakeLSQClient()
    assert run_once(repo, lsq, get_settings()) == 1
    assert repo.status(job_id) == "done"

    # 3. FakeLSQ shows the three fields written IN ORDER: band, score, reason
    assert lsq.order("opp-9") == ["F_BAND", "F_SCORE", "F_REASON"]
    fields = lsq.fields("opp-9")
    assert fields["F_BAND"] == "Clear"
    assert fields["F_SCORE"] == "89.0"
    assert fields["F_REASON"].startswith("Clear —")

    # 4. one result recorded
    assert len(repo.results) == 1


def test_duplicate_event_id_is_not_reprocessed(client, repo):
    first = _post(client, event_id="dup-1")
    assert first.json()["status"] == "accepted"
    job_id = first.json()["job_id"]

    dup = _post(client, event_id="dup-1")
    assert dup.status_code == 200
    assert dup.json()["status"] == "duplicate"
    assert dup.json()["job_id"] == job_id  # same job, no new enqueue

    # Only one job ever exists; draining processes exactly one.
    lsq = FakeLSQClient()
    assert run_once(repo, lsq, get_settings()) == 1
    assert run_once(repo, lsq, get_settings()) == 0  # nothing left
    assert len(repo.results) == 1


def test_worker_degrades_when_tenant_backend_has_no_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    # Tenant configured to a live backend ("groq") with no key set: process_job
    # must degrade to UnavailableVision (-> Doubtful) instead of raising.
    result = _run_one_job(vision_backend="groq")
    assert result.band != "Clear"
    config.get_settings.cache_clear()
