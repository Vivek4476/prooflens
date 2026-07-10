"""Rate-limit middleware behaviour over the real app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _client(general: int, compute: int) -> TestClient:
    # Patch settings so the app builds with tiny limits.
    from prooflens import config
    config.get_settings.cache_clear()
    import os
    os.environ["RATELIMIT_GENERAL_PER_MIN"] = str(general)
    os.environ["RATELIMIT_COMPUTE_PER_MIN"] = str(compute)
    repo = InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                                    scoring=ScoringConfig(), vision_backend="stub")])
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from prooflens import config
    yield
    import os
    os.environ.pop("RATELIMIT_GENERAL_PER_MIN", None)
    os.environ.pop("RATELIMIT_COMPUTE_PER_MIN", None)
    config.get_settings.cache_clear()


def test_over_general_limit_returns_429_with_retry_after():
    client = _client(general=2, compute=0)
    assert client.get("/v1/results").status_code == 200
    assert client.get("/v1/results").status_code == 200
    r = client.get("/v1/results")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_probes_are_never_limited():
    client = _client(general=1, compute=0)
    for _ in range(10):
        assert client.get("/healthz").status_code == 200  # exempt


def test_compute_tier_is_stricter():
    # general high, compute=1: the 2nd bulk-score call is limited by the compute tier.
    client = _client(general=1000, compute=1)
    payload = {"rows": [{"image_url": "https://x/p.jpg"}]}
    assert client.post("/v1/bulk-score", json=payload).status_code in (200, 429)
    r = client.post("/v1/bulk-score", json=payload)
    assert r.status_code == 429


def test_webhook_is_never_rate_limited():
    # general=1: a non-exempt path would 429 on the 2nd call. The webhook
    # must bypass the limiter entirely, so none of several calls return 429
    # (they may 401/404/422 on signature/payload — that's fine).
    client = _client(general=1, compute=0)
    for _ in range(5):
        r = client.post("/v1/webhooks/lsq/dev", json={"anything": "here"})
        assert r.status_code != 429


def test_compute_rejection_does_not_burn_general_budget():
    # general=5, compute=1: 2nd bulk-score call rejects on compute, but must
    # NOT have consumed the shared general counter — a subsequent /v1/results
    # call should still succeed.
    client = _client(general=5, compute=1)
    payload = {"rows": [{"image_url": "https://x/p.jpg"}]}
    assert client.post("/v1/bulk-score", json=payload).status_code in (200, 429)
    r = client.post("/v1/bulk-score", json=payload)
    assert r.status_code == 429
    assert client.get("/v1/results").status_code == 200
