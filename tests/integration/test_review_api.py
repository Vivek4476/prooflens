"""POST /v1/results/{id}/review — records a decision, audits it, filters the queue.
Fully offline: InMemoryRepo + stub backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView
from tests.helpers import IMAGES_DIR


@pytest.fixture
def repo() -> InMemoryRepo:
    t = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    return InMemoryRepo([t])


@pytest.fixture
def client(repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app, raise_server_exceptions=False)


def _score(client) -> str:
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post("/v1/score", files={"image": ("m.jpg", fh.read(), "image/jpeg")})
    return r.json()["result_id"]


def test_review_records_and_returns_block(client):
    rid = _score(client)
    r = client.post(f"/v1/results/{rid}/review", json={"decision": "approve", "note": "ok"})
    assert r.status_code == 200
    review = r.json()["review"]
    assert review["status"] == "approve"
    assert review["reviewer"] == "Demo Operator"
    assert review["reviewed_at"] and review["note"] == "ok"


def test_review_unknown_result_404(client):
    r = client.post("/v1/results/does-not-exist/review", json={"decision": "approve"})
    assert r.status_code == 404


def test_review_invalid_decision_422(client):
    rid = _score(client)
    r = client.post(f"/v1/results/{rid}/review", json={"decision": "banana"})
    assert r.status_code == 422


def test_review_writes_audit_log(client, repo):
    rid = _score(client)
    client.post(f"/v1/results/{rid}/review", json={"decision": "reject"})
    assert repo.audit_log[-1]["event"] == "review.decision"
    assert repo.audit_log[-1]["detail"]["decision"] == "reject"


def test_results_review_filter_hides_actioned(client):
    rid = _score(client)
    client.post(f"/v1/results/{rid}/review", json={"decision": "approve"})
    pending = client.get("/v1/results", params={"review": "pending"}).json()
    assert all(i["review"] is None for i in pending["items"])
    assert rid not in [i["id"] for i in pending["items"]]


def test_get_result_includes_review_block(client):
    rid = _score(client)
    assert client.get(f"/v1/results/{rid}").json()["review"] is None
