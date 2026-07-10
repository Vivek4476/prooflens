"""End-to-end: tenant A's key sees only A's results, never B's."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant(tid: str) -> TenantView:
    return TenantView(id=tid, slug=tid, webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _seed(repo, tid: str, n: int) -> None:
    for i in range(n):
        repo.results.append(ResultView(
            id=f"{tid}-{i}", created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
            tenant_id=tid, band="Clear", score=90.0, reason="r",
            reason_code="clear", rubric_version="v3", rep_id="A1",
        ))


@pytest.fixture
def env():
    repo = InMemoryRepo([_tenant("t1"), _tenant("t2")])
    _seed(repo, "t1", 3)
    _seed(repo, "t2", 5)
    key_a = generate_key()
    repo.record_api_key("t1", hash_key(key_a), key_prefix(key_a), "A")
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    # NOTE: require_tenant is NOT overridden here — we exercise the real header path.
    return TestClient(app, raise_server_exceptions=False), key_a


def test_no_key_is_401(env):
    client, _ = env
    assert client.get("/v1/results").status_code == 401


def test_key_a_sees_only_tenant_a(env):
    client, key_a = env
    r = client.get("/v1/results", headers={"Authorization": f"Bearer {key_a}"})
    assert r.status_code == 200
    assert r.json()["total"] == 3  # A's rows only, never B's 5


def test_bad_key_is_401(env):
    client, _ = env
    r = client.get("/v1/results", headers={"Authorization": "Bearer pl_wrong"})
    assert r.status_code == 401
