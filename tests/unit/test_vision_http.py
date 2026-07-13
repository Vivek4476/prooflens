"""Shared chat-completions POST helper: happy path + error mapping."""
from __future__ import annotations

import json
import urllib.error

import pytest

from prooflens.vision import _http
from prooflens.vision._http import VisionUnavailable, post_chat


class _FakeResp:
    headers = {"cf-ray": "ray-123"}

    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_post_chat_returns_data_and_request_id(monkeypatch):
    def fake_urlopen(req, timeout):
        assert json.loads(req.data)["model"] == "m"
        return _FakeResp({"id": "gen-1", "choices": []})

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    data, request_id = post_chat(
        invoke_url="https://x/chat/completions", api_key="k",
        payload={"model": "m"}, timeout=5.0, name="scout", model="m",
    )
    assert data["id"] == "gen-1"
    assert request_id == "ray-123"


def test_post_chat_maps_http_error_to_vision_unavailable(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(VisionUnavailable) as ei:
        post_chat(invoke_url="https://x/chat/completions", api_key="k",
                  payload={}, timeout=5.0, name="scout", model="m")
    assert ei.value.status == 429
