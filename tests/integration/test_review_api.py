"""POST /v1/results/{id}/review — records a decision, audits it, filters the queue.
Fully offline: InMemoryRepo + stub backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
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
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
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


# --- gating / cross-tenant scoping (final review, Finding 1) ---
# These use a client WITHOUT the require_tenant override, exercising the real
# Authorization: Bearer header path end-to-end.


@pytest.fixture
def real_auth_env():
    """Two tenants, no require_tenant override — the real Bearer-key path."""
    t1 = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    t2 = TenantView(id="t2", slug="other", webhook_secret="s", field_map={},
                     scoring=ScoringConfig())
    repo = InMemoryRepo([t1, t2])
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    client = TestClient(app, raise_server_exceptions=False)

    key_a = generate_key()
    repo.record_api_key("t1", hash_key(key_a), key_prefix(key_a), "A")
    key_b = generate_key()
    repo.record_api_key("t2", hash_key(key_b), key_prefix(key_b), "B")

    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        image_bytes = fh.read()
    r = client.post(
        "/v1/score",
        files={"image": ("m.jpg", image_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {key_a}"},
    )
    rid_a = r.json()["result_id"]
    return client, key_a, key_b, rid_a


def test_get_result_no_auth_header_is_401(real_auth_env):
    client, _key_a, _key_b, rid_a = real_auth_env
    r = client.get(f"/v1/results/{rid_a}")
    assert r.status_code == 401


def test_review_result_no_auth_header_is_401(real_auth_env):
    client, _key_a, _key_b, rid_a = real_auth_env
    r = client.post(f"/v1/results/{rid_a}/review", json={"decision": "approve"})
    assert r.status_code == 401


def test_get_result_wrong_tenant_key_is_404(real_auth_env):
    client, _key_a, key_b, rid_a = real_auth_env
    r = client.get(f"/v1/results/{rid_a}", headers={"Authorization": f"Bearer {key_b}"})
    assert r.status_code == 404  # honest 404 — never confirm cross-tenant existence


def test_review_result_wrong_tenant_key_is_404(real_auth_env):
    client, _key_a, key_b, rid_a = real_auth_env
    r = client.post(
        f"/v1/results/{rid_a}/review",
        json={"decision": "approve"},
        headers={"Authorization": f"Bearer {key_b}"},
    )
    assert r.status_code == 404
