"""Judgment validates + coerces the reasoner's 4 output fields."""
from __future__ import annotations

from prooflens.vision.schema import Judgment


def test_judgment_coerces_and_clamps():
    j = Judgment(plausibility="85", visit_context="150",
                 context_confidence="MEDIUM", reason=None)
    assert j.plausibility == 85
    assert j.visit_context == 100          # clamped to 0-100
    assert j.context_confidence == "moderate"  # "medium" -> "moderate"
    assert j.reason == ""


def test_judgment_missing_visit_context_is_none():
    j = Judgment(plausibility=40, context_confidence="low")
    assert j.visit_context is None
