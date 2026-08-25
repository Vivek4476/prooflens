from prooflens.engine.summarize import summarize_decision
from prooflens.engine.types import CheckOutcome, Verdict


def _v(band, reason_code, reason, checks):
    return Verdict(score=0, band=band, reason=reason, reason_code=reason_code,
                   checks=checks, rubric_version="v3")


def test_clear_decision_reads_positive():
    v = _v("Clear", "clear", "Genuine meeting photo",
           [CheckOutcome(name="content", available=True, score=90, summary="two people, meeting")])
    out = summarize_decision(v)
    assert "Clear" in out
    assert len(out) <= 400


def test_suspect_names_the_deciding_signal():
    v = _v(
        "Suspect",
        "recycled",
        "Reused image",
        [
            CheckOutcome(
                name="uniqueness",
                available=True,
                score=5,
                summary="near-duplicate of 3 prior",
            )
        ],
    )
    out = summarize_decision(v)
    assert "duplicate" in out.lower() or "reused" in out.lower()


def test_unassessed_explains_no_grade():
    v = _v("Unassessed", "no_content_analysis", "Vision check unavailable",
           [CheckOutcome(name="content", available=False, score=None, summary="")])
    out = summarize_decision(v)
    assert "not graded" in out.lower()


def test_is_deterministic():
    v = _v("Doubtful", "single_person", "Only one person",
           [CheckOutcome(name="content", available=True, score=55, summary="one face")])
    assert summarize_decision(v) == summarize_decision(v)


def test_unknown_reason_code_falls_back_to_verdict_reason():
    v = _v("Doubtful", "future_code_xyz", "Some new reason", [])
    assert "some new reason" in summarize_decision(v).lower()


def test_long_evidence_is_capped_at_400():
    long = "word " * 200
    v = _v("Suspect", "recycled", "Reused",
           [CheckOutcome(name="uniqueness", available=True, score=1, summary=long)])
    assert len(summarize_decision(v)) <= 400


def test_never_raises_when_reason_is_none():
    v = _v("Suspect", "totally_unknown_code", None, [])  # None reason + unknown code
    out = summarize_decision(v)
    assert isinstance(out, str)
