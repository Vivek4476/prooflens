"""UnavailableVision raises on assess so the relevance check degrades gracefully."""
from __future__ import annotations

import pytest

from prooflens.engine.checks import relevance
from prooflens.engine.scoring_config import Thresholds
from prooflens.vision.unavailable import UnavailableVision


def test_assess_raises_with_reason():
    v = UnavailableVision("no GROQ_API_KEY set")
    assert v.is_real is False
    with pytest.raises(RuntimeError, match="no GROQ_API_KEY set"):
        v.assess(b"\xff\xd8\xff")


def test_relevance_reports_unavailable_when_backend_raises():
    outcome = relevance.run(b"\xff\xd8\xff", vision=UnavailableVision("boom"), thresholds=Thresholds())
    assert outcome.available is False
    assert outcome.score is None
    assert outcome.data.get("error") is True
    assert "boom" in outcome.data.get("detail", "")
