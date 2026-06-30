"""Tests for fusion + the relevance check with a MOCKED vision backend."""

from checks.types import CheckResult
from checks import relevance
from vision.base import VisionBackend, normalize
import fusion


class FakeBackend(VisionBackend):
    """A mock vision backend returning a canned verdict — no network."""

    name = "fake"
    is_real = True

    def __init__(self, raw):
        self._raw = raw

    def assess(self, image_bytes):
        return normalize(self._raw, backend=self.name, model="fake-1")


def _good_verdict():
    return {
        "people_count": 3,
        "setting": "office",
        "primary_subject": "people meeting",
        "people_present": True,
        "looks_like_photo_of_a_screen": False,
        "is_designed_graphic": False,
        "is_meme_or_screenshot": False,
        "meeting_plausibility": 88,
        "reason": "Three people around a table.",
    }


def _all_pass_checks():
    return [
        CheckResult("sharpness", True, 90, "sharp", metric=300.0),
        CheckResult("person_presence", True, 100, "person", metric=2.0),
        CheckResult("uniqueness", True, 100, "unique", metric=20.0),
        CheckResult("metadata", True, 85, "exif"),
    ]


# ---------------------------------------------------------------- relevance
def test_relevance_good_scene_passes():
    res, verdict = relevance.assess(b"x", backend=FakeBackend(_good_verdict()))
    assert res.passed is True
    assert res.score == 88
    assert verdict["meeting_plausibility"] == 88


def test_relevance_screen_photo_is_capped_and_fails():
    raw = _good_verdict()
    raw["looks_like_photo_of_a_screen"] = True
    res, _ = relevance.assess(b"x", backend=FakeBackend(raw))
    assert res.passed is False
    assert res.score <= 25


# ---------------------------------------------------------------- fusion
def test_fuse_clear_for_good_inputs():
    content, verdict = relevance.assess(b"x", backend=FakeBackend(_good_verdict()))
    checks = [content] + _all_pass_checks()
    fused = fusion.fuse(checks, verdict)
    assert fused.band == "Clear"
    assert fused.score >= 70
    assert fused.gates_fired == []


def test_fuse_screen_gate_forces_suspect():
    raw = _good_verdict()
    raw["looks_like_photo_of_a_screen"] = True
    content, verdict = relevance.assess(b"x", backend=FakeBackend(raw))
    checks = [content] + _all_pass_checks()
    fused = fusion.fuse(checks, verdict)
    assert "photo_of_screen" in fused.gates_fired
    assert fused.score <= 20
    assert fused.band == "Suspect"


def test_fuse_duplicate_gate():
    content, verdict = relevance.assess(b"x", backend=FakeBackend(_good_verdict()))
    checks = [content] + _all_pass_checks()
    # Force the uniqueness check to look like an exact duplicate.
    for c in checks:
        if c.name == "uniqueness":
            c.metric = 0.0
            c.score = 0.0
    fused = fusion.fuse(checks, verdict)
    assert "exact_duplicate" in fused.gates_fired
    assert fused.band == "Suspect"


def test_fuse_low_plausibility_gate():
    raw = _good_verdict()
    raw["meeting_plausibility"] = 10
    content, verdict = relevance.assess(b"x", backend=FakeBackend(raw))
    checks = [content] + _all_pass_checks()
    fused = fusion.fuse(checks, verdict)
    assert "low_meeting_plausibility" in fused.gates_fired
    assert fused.score <= 25
