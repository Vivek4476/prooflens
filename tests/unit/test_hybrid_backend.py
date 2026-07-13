"""HybridBackend: merge, stage-2 fallback, stage-1 propagation."""
from __future__ import annotations

import pytest

from prooflens.vision._http import VisionUnavailable
from prooflens.vision.hybrid import HybridBackend
from prooflens.vision.schema import ContentAssessment, Judgment

_SCOUT = ContentAssessment(
    people_count=2, setting="office", scene_description="two at a desk",
    plausibility=50, visit_context=40, context_confidence="low", reason="scout view",
)


def _make(monkeypatch, *, scout_result=None, scout_exc=None,
          reason_result=None, reason_exc=None):
    hb = HybridBackend(api_key="k", base_url="https://cf/ai/v1",
                       vision_model="scout-m", reasoner_model="reason-m")

    def scout_assess(_img):
        if scout_exc:
            raise scout_exc
        return scout_result

    def reason_refine(_perc):
        if reason_exc:
            raise reason_exc
        return reason_result

    monkeypatch.setattr(hb.scout, "assess", scout_assess)
    monkeypatch.setattr(hb.reasoner, "refine", reason_refine)
    return hb


def test_happy_path_merges_reasoner_judgment(monkeypatch):
    j = Judgment(plausibility=90, visit_context=85, context_confidence="high",
                 reason="clear two-way interaction")
    hb = _make(monkeypatch, scout_result=_SCOUT, reason_result=j)
    out = hb.assess(b"img")
    assert out.plausibility == 90 and out.visit_context == 85
    assert out.context_confidence == "high" and out.reason == "clear two-way interaction"
    assert out.scene_description == "two at a desk"     # perception preserved
    assert out.backend == "hybrid" and out.model == "scout-m+reason-m"


def test_stage2_failure_keeps_scout_judgment(monkeypatch):
    hb = _make(monkeypatch, scout_result=_SCOUT,
               reason_exc=VisionUnavailable("429", status=429))
    out = hb.assess(b"img")
    assert out.plausibility == 50 and out.reason == "scout view"   # Scout's own
    assert out.backend == "hybrid"
    assert "reasoner-unavailable" in out.model


def test_stage2_bad_json_keeps_scout_judgment(monkeypatch):
    hb = _make(monkeypatch, scout_result=_SCOUT, reason_exc=ValueError("bad json"))
    out = hb.assess(b"img")
    assert out.plausibility == 50 and out.backend == "hybrid"


def test_stage1_failure_propagates(monkeypatch):
    hb = _make(monkeypatch, scout_exc=VisionUnavailable("down", status=503))
    with pytest.raises(VisionUnavailable):
        hb.assess(b"img")
