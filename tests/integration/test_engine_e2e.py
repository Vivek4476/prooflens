"""End-to-end engine behaviour, fully offline (stub backend, in-memory store)."""

from __future__ import annotations

from prooflens.engine import InMemoryHashStore
from prooflens.vision import get_backend
from tests.helpers import IMAGES_DIR, score_image


def test_free_hard_gate_skips_the_paid_vision_call():
    # The screen-recapture image trips a free gate; the content check must be
    # skipped (never spend on the paid call for an obvious reject).
    v = score_image(IMAGES_DIR / "screen_recapture.jpg",
                    store=InMemoryHashStore(), backend=get_backend("stub"))
    content = next(c for c in v.checks if c.name == "content")
    assert content.available is False
    assert content.data.get("skipped") is True


def test_clean_image_runs_content_and_labels_stub():
    v = score_image(IMAGES_DIR / "meeting.jpg",
                    store=InMemoryHashStore(), backend=get_backend("stub"))
    content = next(c for c in v.checks if c.name == "content")
    assert content.available is True
    assert content.data["is_real_backend"] is False  # honestly labelled as a stub


def test_full_verdict_shape():
    v = score_image(IMAGES_DIR / "meeting.jpg",
                    store=InMemoryHashStore(), backend=get_backend("stub"))
    d = v.to_dict()
    assert set(d) == {"band", "score", "reason", "reason_code", "checks", "rubric_version"}
    assert {c["name"] for c in d["checks"]} == {
        "exif", "sharpness", "uniqueness", "recapture", "content"
    }


def test_tenant_isolation_no_cross_tenant_duplicate():
    store = InMemoryHashStore()
    backend = get_backend("stub")
    # Same image under two tenants: neither should see the other's upload.
    a = score_image(IMAGES_DIR / "duplicate_a.jpg", store=store, backend=backend, tenant_id="A")
    b = score_image(IMAGES_DIR / "duplicate_b.jpg", store=store, backend=backend, tenant_id="B")
    assert a.reason_code == "clear"
    assert b.reason_code == "clear"
