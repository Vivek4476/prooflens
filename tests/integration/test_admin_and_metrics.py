"""Admin auth + /metrics — offline (no DB access needed for these paths)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from prooflens.api.app import create_app

client = TestClient(create_app(), raise_server_exceptions=False)


def test_admin_requires_valid_token():
    # No token -> 401 (require_admin runs before any DB access).
    r = client.post("/admin/tenants", json={"slug": "x", "name": "X", "webhook_secret": "s"})
    assert r.status_code == 401

    r2 = client.post(
        "/admin/tenants",
        headers={"X-Admin-Token": "wrong"},
        json={"slug": "x", "name": "X", "webhook_secret": "s"},
    )
    assert r2.status_code == 401


def test_metrics_endpoint_serves_prometheus():
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    # Metric families are registered at import, so their HELP/TYPE lines appear
    # even before any samples — the endpoint works without a database.
    assert "prooflens_band_total" in body
    assert "prooflens_queue_depth" in body
