"""The additive frontend API: /v1/score, /v1/results, /v1/analytics/summary.

Fully offline: InMemoryRepo + stub backend (no DB, no network, no paid model).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView
from tests.helpers import IMAGES_DIR


def _tenant() -> TenantView:
    return TenantView(
        id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig(),
        vision_backend="stub",
    )


@pytest.fixture
def repo() -> InMemoryRepo:
    return InMemoryRepo([_tenant()])


@pytest.fixture
def client(repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app, raise_server_exceptions=False)


def _upload(client, name):
    with open(IMAGES_DIR / name, "rb") as fh:
        return client.post("/v1/score", files={"image": (name, fh.read(), "image/jpeg")})


def test_score_returns_real_verdict(client):
    r = _upload(client, "meeting.jpg")
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == "Clear"
    assert body["reason"].startswith("Clear")
    assert body["backend"] == "stub" and body["backend_is_real"] is False
    # checks[] is the truth surface for explainability
    assert {c["name"] for c in body["checks"]} == {
        "exif", "sharpness", "uniqueness", "recapture", "content"
    }
    assert body["processing_ms"] >= 0
    assert body["rubric_version"] == "v3"


def test_get_single_result_returns_full_evidence(client):
    rid = _upload(client, "meeting.jpg").json()["result_id"]
    r = client.get(f"/v1/results/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == rid
    assert body["band"] == "Clear"
    # the detail view carries the full checks[] evidence, not just a summary
    assert {c["name"] for c in body["checks"]} == {
        "exif", "sharpness", "uniqueness", "recapture", "content"
    }


def test_get_missing_result_404(client):
    assert client.get("/v1/results/does-not-exist").status_code == 404


def test_demo_model_always_scores(client):
    # "Demo Model" (stub) is always available and never surfaces an AI error.
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post(
            "/v1/score",
            files={"image": ("m.jpg", fh.read(), "image/jpeg")},
            data={"backend": "stub"},
        )
    assert r.status_code == 200
    assert r.json()["backend"] == "stub"


def test_live_ai_unconfigured_surfaces_error_not_stub(client):
    # Live AI selected but the backend can't be built (unknown/unconfigured) must
    # NOT fall back to the stub — it surfaces the exact reason as a 503.
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post(
            "/v1/score",
            files={"image": ("m.jpg", fh.read(), "image/jpeg")},
            data={"backend": "not_a_real_backend"},
        )
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    assert "not_a_real_backend" in detail and "unavailable" in detail


def test_live_ai_call_failure_surfaces_exact_reason(client, monkeypatch):
    # When the model call itself fails (e.g. 429), surface the provider's exact
    # reason as a 503 — never a stub verdict, never a generic message.
    from prooflens.config import Settings

    class Boom:
        is_real = True
        name = "openrouter"

        def assess(self, image_bytes):
            raise RuntimeError("openrouter API error 429: rate limited")

    monkeypatch.setattr(Settings, "build_vision_backend", lambda self, name=None: Boom())
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post(
            "/v1/score",
            files={"image": ("m.jpg", fh.read(), "image/jpeg")},
            data={"backend": "openrouter"},
        )
    assert r.status_code == 503
    assert "429" in r.json()["detail"]


def test_default_path_without_key_caps_to_doubtful(client, monkeypatch):
    # Default backend groq, but no key configured -> vision unavailable.
    monkeypatch.setenv("VISION_BACKEND", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    r = _upload(client, "meeting.jpg")
    assert r.status_code == 200                     # never blocks
    body = r.json()
    assert body["band"] != "Clear"                  # never a fake Clear
    content = next(c for c in body["checks"] if c["name"] == "content")
    assert content["available"] is False
    config.get_settings.cache_clear()


def test_explicit_override_to_misconfigured_live_backend_503s(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post(
            "/v1/score",
            files={"image": ("meeting.jpg", fh.read(), "image/jpeg")},
            data={"backend": "groq"},               # operator explicitly asked for groq
        )
    assert r.status_code == 503
    config.get_settings.cache_clear()


def test_score_unknown_tenant_404(client):
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post("/v1/score", files={"image": ("m.jpg", fh.read(), "image/jpeg")},
                        data={"tenant": "nope"})
    assert r.status_code == 404


def test_results_and_analytics_populate(client):
    _upload(client, "meeting.jpg")
    _upload(client, "screenshot.jpg")
    _upload(client, "landscape.jpg")

    res = client.get("/v1/results?limit=10").json()
    assert res["total"] == 3
    assert len(res["items"]) == 3
    # newest first
    assert res["items"][0]["source"] == "direct"

    # band filter
    suspect = client.get("/v1/results?band=Suspect").json()
    assert suspect["total"] >= 2  # screenshot + landscape

    summary = client.get("/v1/analytics/summary").json()
    assert summary["total"] == 3
    assert summary["band_distribution"]["Clear"] == 1
    assert summary["images_today"] == 3
    assert any(tr["reason_code"] == "designed_graphic" for tr in summary["top_reasons"])
    assert summary["series"]  # at least one day bucket
