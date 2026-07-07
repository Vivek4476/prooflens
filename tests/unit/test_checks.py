"""Deterministic check behaviour on the golden images + engine invariants."""

from __future__ import annotations

from prooflens.engine import DEFAULT_SCORING, InMemoryHashStore
from prooflens.engine.checks import blur, recapture, uniqueness
from prooflens.engine.hashstore import hamming_hex
from prooflens.vision import get_backend
from tests.helpers import IMAGES_DIR, score_image


def _bytes(name):
    return (IMAGES_DIR / name).read_bytes()


def test_blur_flags_blurred_not_sharp():
    blurred = blur.run(_bytes("blurred.jpg"), DEFAULT_SCORING.thresholds)
    meeting = blur.run(_bytes("meeting.jpg"), DEFAULT_SCORING.thresholds)
    assert blurred.data["too_blurred"] is True
    assert meeting.data["too_blurred"] is False


def test_recapture_only_fires_on_screen_image():
    fired = recapture.run(_bytes("screen_recapture.jpg"))
    clean = recapture.run(_bytes("meeting.jpg"))
    assert fired.data["screen_detected"] is True
    assert clean.data["screen_detected"] is False


def test_uniqueness_exact_duplicate():
    store = InMemoryHashStore()
    t = DEFAULT_SCORING.thresholds
    first = uniqueness.run(_bytes("duplicate_a.jpg"), tenant_id="dev", store=store, thresholds=t)
    store.remember("dev", first.data["dhash"])
    second = uniqueness.run(_bytes("duplicate_b.jpg"), tenant_id="dev", store=store, thresholds=t)
    assert second.data["exact_duplicate"] is True


def test_uniqueness_is_tenant_scoped():
    store = InMemoryHashStore()
    t = DEFAULT_SCORING.thresholds
    r = uniqueness.run(_bytes("duplicate_a.jpg"), tenant_id="A", store=store, thresholds=t)
    store.remember("A", r.data["dhash"])
    # Same image, different tenant -> no match.
    other = uniqueness.run(_bytes("duplicate_b.jpg"), tenant_id="B", store=store, thresholds=t)
    assert other.data["distance"] is None


def test_hamming_hex():
    assert hamming_hex("00", "00") == 0
    assert hamming_hex("0f", "00") == 4


def test_engine_stamps_rubric_version_and_orders_output():
    store = InMemoryHashStore()
    v = score_image(IMAGES_DIR / "meeting.jpg", store=store, backend=get_backend("stub"))
    assert v.rubric_version == "v3"
    d = v.to_dict()
    # verdict first, evidence second, internals last
    keys = list(d.keys())
    assert keys.index("band") < keys.index("checks") < keys.index("rubric_version")


def test_never_stores_images_only_hash_and_trail():
    store = InMemoryHashStore()
    score_image(IMAGES_DIR / "meeting.jpg", store=store, backend=get_backend("stub"),
                rep_id="rep-1", opportunity_id="opp-9")
    rows = store._rows["dev"]
    assert len(rows) == 1
    dhash, rep, opp, _ = rows[0]
    assert len(dhash) == 16 and rep == "rep-1" and opp == "opp-9"  # 64-bit dHash, trail only
