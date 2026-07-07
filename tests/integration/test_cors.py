"""CORS allows every Vercel deployment of this project via allow_origin_regex,
so a fresh preview/deploy URL isn't blocked by exact-match origins."""

from __future__ import annotations

from fastapi.testclient import TestClient

from prooflens.api.app import create_app

# A per-deployment Vercel URL (NOT in the exact cors_origins list) — the class of
# URL that produced the browser "Network Error" before the regex was added.
PREVIEW = "https://prooflens-abc123xyz-vivek4476s-projects.vercel.app"
CANON = "https://prooflens-vivek4476s-projects.vercel.app"


def _client() -> TestClient:
    return TestClient(create_app())


def test_preview_vercel_origin_allowed_by_regex():
    r = _client().options(
        "/v1/score",
        headers={
            "Origin": PREVIEW,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == PREVIEW


def test_canonical_vercel_origin_allowed():
    r = _client().options(
        "/v1/score",
        headers={"Origin": CANON, "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == CANON


def test_unrelated_origin_not_allowed():
    r = _client().options(
        "/v1/score",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    # No allow-origin echoed for a non-matching origin.
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"
