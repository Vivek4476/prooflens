"""Fusion logic — blend, hard-gate floors, reason selection."""

from __future__ import annotations

from prooflens.engine import DEFAULT_SCORING
from prooflens.engine.fusion import fuse
from prooflens.engine.types import CheckOutcome
from prooflens.engine.verdicts import Reason


def _content(**data):
    base = {
        "people_count": 2,
        "plausibility": 80,
        "looks_like_photo_of_a_screen": False,
        "is_designed_graphic": False,
        "is_meme_or_screenshot": False,
    }
    base.update(data)
    return CheckOutcome("content", available=True, score=float(base["plausibility"]),
                        summary="", data=base)


def _co(name, score, **data):
    return CheckOutcome(name, available=True, score=score, summary="", data=data)


def _clean_checks():
    return [
        _co("exif", 60.0),
        _co("sharpness", 100.0, too_blurred=False),
        _co("uniqueness", 100.0, exact_duplicate=False, near_duplicate=False),
        _co("recapture", 100.0, screen_detected=False),
        _content(),
    ]


def test_clean_scene_is_clear():
    r = fuse(_clean_checks(), DEFAULT_SCORING)
    assert r.band == "Clear"
    assert r.reason_code == Reason.CLEAR.value


def test_exact_duplicate_gates_to_suspect():
    checks = _clean_checks()
    checks[2] = _co("uniqueness", 0.0, exact_duplicate=True, near_duplicate=False)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Suspect"
    assert r.reason_code == Reason.RECYCLED.value


def test_screen_recapture_gate():
    checks = _clean_checks()
    checks[3] = _co("recapture", 0.0, screen_detected=True)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Suspect"
    assert r.reason_code == Reason.SCREEN_RECAPTURE.value


def test_no_people_gate():
    checks = _clean_checks()
    checks[4] = _content(people_count=0, plausibility=20)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Suspect"
    assert r.reason_code == Reason.NO_PEOPLE_OR_IRRELEVANT.value


def test_blur_is_a_soft_quality_gate_not_suspect():
    checks = _clean_checks()
    checks[1] = _co("sharpness", 0.0, too_blurred=True)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"  # never a heavy penalty on its own
    assert r.reason_code == Reason.TOO_BLURRED.value


def test_fraud_outranks_blur():
    checks = _clean_checks()
    checks[1] = _co("sharpness", 0.0, too_blurred=True)
    checks[2] = _co("uniqueness", 0.0, exact_duplicate=True, near_duplicate=False)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.reason_code == Reason.RECYCLED.value  # recycled beats too_blurred


def test_vision_unavailable_never_clear():
    checks = _clean_checks()
    checks[4] = CheckOutcome("content", available=False, score=None, summary="",
                             data={"error": True})
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band != "Clear"
    assert r.reason_code == Reason.NO_CONTENT_ANALYSIS.value
