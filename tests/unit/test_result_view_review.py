"""ResultView.to_dict() surfaces a review block only once a decision exists."""

from __future__ import annotations

from prooflens.service.views import ResultView


def _view(**kw) -> ResultView:
    base = dict(
        id="r1", created_at="2026-07-07T00:00:00+00:00", tenant_id="t1",
        band="Suspect", score=20.0, reason="Suspect — designed graphic",
        reason_code="designed_graphic", rubric_version="v1",
    )
    base.update(kw)
    return ResultView(**base)


def test_review_is_none_when_undecided():
    assert _view().to_dict()["review"] is None


def test_review_block_present_after_decision():
    d = _view(
        review_status="approve", review_note="looks fine",
        reviewed_at="2026-07-07T01:00:00+00:00", reviewer="Demo Operator",
    ).to_dict()
    assert d["review"] == {
        "status": "approve",
        "note": "looks fine",
        "reviewed_at": "2026-07-07T01:00:00+00:00",
        "reviewer": "Demo Operator",
    }
