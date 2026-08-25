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
    assert "unassess" in out.lower() or "not graded" in out.lower() or "unavailable" in out.lower()


def test_is_deterministic():
    v = _v("Doubtful", "single_person", "Only one person",
           [CheckOutcome(name="content", available=True, score=55, summary="one face")])
    assert summarize_decision(v) == summarize_decision(v)
