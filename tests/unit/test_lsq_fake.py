"""FakeLSQClient records ordered custom-field writes."""

from __future__ import annotations

from prooflens.lsq import FakeLSQClient, FieldUpdate


def test_records_writes_in_order():
    lsq = FakeLSQClient()
    lsq.update_custom_fields(
        "opp-1",
        [FieldUpdate("F_BAND", "Clear"), FieldUpdate("F_SCORE", "89.0"),
         FieldUpdate("F_REASON", "all good")],
    )
    assert lsq.order("opp-1") == ["F_BAND", "F_SCORE", "F_REASON"]
    assert lsq.fields("opp-1") == {"F_BAND": "Clear", "F_SCORE": "89.0", "F_REASON": "all good"}


def test_is_labelled_not_real():
    assert FakeLSQClient().is_real is False
