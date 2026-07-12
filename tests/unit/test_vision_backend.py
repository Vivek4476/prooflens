"""OpenAI-compatible vision backend — request shape."""

from __future__ import annotations

import json

from prooflens.vision import openai_compat
from prooflens.vision.openai_compat import OpenAICompatBackend

_VALID = {
    "people_count": 2,
    "plausibility": 80,
    "visit_context": 70,
    "context_confidence": "high",
    "scene_description": "two people at a desk",
}


class _FakeResp:
    headers: dict = {}

    def __init__(self, content: str):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {"id": "gen-1", "choices": [{"message": {"content": self._content}}]}
        ).encode()


def test_payload_is_deterministic_temperature_zero(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data)
        return _FakeResp(json.dumps(_VALID))

    monkeypatch.setattr(openai_compat.urllib.request, "urlopen", fake_urlopen)

    backend = OpenAICompatBackend(
        name="groq", api_key="k", model="m", base_url="https://api.example.com"
    )
    out = backend.assess(b"not-a-real-image")  # resize_for_model fails open to raw bytes

    assert captured["body"]["temperature"] == 0.0  # deterministic by default
    assert out.plausibility == 80 and out.people_count == 2
