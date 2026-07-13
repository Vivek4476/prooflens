"""Reasoner sends perception-as-text (no image) and parses a Judgment."""
from __future__ import annotations

import json

from prooflens.vision import _http
from prooflens.vision.reasoner import Reasoner
from prooflens.vision.schema import ContentAssessment, Judgment

_PERCEPTION = ContentAssessment(
    people_count=2, people_interacting=True, setting="office",
    scene_description="two people at a desk with paperwork", plausibility=50,
)


class _FakeResp:
    headers: dict = {}

    def __init__(self, content: str):
        self._c = content

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps({"id": "r-1", "choices": [{"message": {"content": self._c}}]}).encode()


def test_refine_sends_no_image_and_returns_judgment(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data)
        return _FakeResp(json.dumps(
            {"plausibility": 90, "visit_context": 80, "context_confidence": "high",
             "reason": "two people interacting over paperwork"}
        ))

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    r = Reasoner(api_key="k", model="@cf/openai/gpt-oss-120b",
                 base_url="https://api.example.com")
    out = r.refine(_PERCEPTION)

    body = json.dumps(captured["body"])
    assert "image_url" not in body                       # text-only
    assert "two people at a desk" in body                # perception embedded
    assert captured["body"]["temperature"] == 0.0
    assert isinstance(out, Judgment)
    assert out.plausibility == 90 and out.visit_context == 80
