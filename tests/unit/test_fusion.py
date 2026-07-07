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


def test_single_person_is_not_a_meeting_doubtful():
    # A lone individual — real photo, but not evidence of a customer meeting.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=1, plausibility=85, visit_context=30, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"  # flagged for review, never Suspect (it's a real photo)
    assert r.reason_code == Reason.SINGLE_PERSON.value


def test_single_person_low_confidence_does_not_gate():
    checks = _clean_checks()
    checks[4] = _content(
        people_count=1, plausibility=85, visit_context=30, context_confidence="low"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.reason_code != Reason.SINGLE_PERSON.value


def test_no_visit_context_gates_to_doubtful_not_suspect():
    # A real photo of real people, but the model is confident there's no visit.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=2, plausibility=85, visit_context=15, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"  # never Suspect — it IS a real capture
    assert r.reason_code == Reason.NO_VISIT_CONTEXT.value


def test_clearly_not_a_visit_gates_to_suspect():
    # The pool case: a real, confident capture whose visit_context is near-absent
    # (a shirtless man at a pool). Clearly not a customer visit -> Suspect.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=1, plausibility=100, visit_context=0, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Suspect"
    assert r.reason_code == Reason.NOT_A_VISIT.value  # outranks single_person


def test_group_clearly_not_a_visit_gates_to_suspect():
    checks = _clean_checks()
    checks[4] = _content(
        people_count=3, plausibility=95, visit_context=5, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Suspect"
    assert r.reason_code == Reason.NOT_A_VISIT.value


def test_borderline_visit_context_stays_doubtful():
    # 15 <= visit_context < 35: weak but not clearly-absent -> Doubtful, NOT Suspect.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=2, plausibility=85, visit_context=20, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"
    assert r.reason_code == Reason.NO_VISIT_CONTEXT.value


def test_low_confidence_irrelevance_is_doubtful_not_suspect():
    # Near-absent visit_context but the model is unsure: no HARD flag, but the scene
    # still reads as clearly-not-a-visit -> route to review (Doubtful), never Suspect.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=1, plausibility=100, visit_context=0, context_confidence="low"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"
    assert r.reason_code == Reason.NO_VISIT_CONTEXT.value
    assert r.reason_code != Reason.NOT_A_VISIT.value  # never the Suspect reason


def test_moderate_confidence_irrelevance_is_doubtful():
    # "moderate" (the schema default) is also not "high" -> Doubtful, not Suspect.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=2, plausibility=90, visit_context=5, context_confidence="moderate"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Doubtful"
    assert r.reason_code == Reason.NO_VISIT_CONTEXT.value


def test_ambiguous_visit_context_does_not_gate():
    # Low visit_context but the model is NOT confident -> reduce confidence,
    # never manufacture a flag. The gate must not fire.
    checks = _clean_checks()
    checks[4] = _content(
        people_count=2, plausibility=85, visit_context=15, context_confidence="low"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.reason_code != Reason.NO_VISIT_CONTEXT.value


def test_missing_visit_context_never_penalised():
    # An older backend omits visit_context entirely (None) -> no gate, stays Clear.
    checks = _clean_checks()
    checks[4] = _content(people_count=2, plausibility=85, visit_context=None)
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Clear"
    assert r.reason_code == Reason.CLEAR.value


def test_strong_visit_context_is_clear():
    checks = _clean_checks()
    checks[4] = _content(
        people_count=2, plausibility=88, visit_context=85, context_confidence="high"
    )
    r = fuse(checks, DEFAULT_SCORING)
    assert r.band == "Clear"


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
