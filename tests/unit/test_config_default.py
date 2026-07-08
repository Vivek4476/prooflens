"""The default vision backend is groq; stub is only reachable by explicit name."""
from __future__ import annotations

import prooflens.config as config


def test_default_backend_is_groq(monkeypatch):
    # Clear the conftest stub-pin so we observe the real default.
    monkeypatch.delenv("VISION_BACKEND", raising=False)
    config.get_settings.cache_clear()
    assert config.Settings().vision_backend == "groq"


def test_stub_still_selectable_by_name():
    settings = config.Settings()
    backend = settings.build_vision_backend("stub")
    assert backend.name == "stub"
    assert backend.is_real is False
