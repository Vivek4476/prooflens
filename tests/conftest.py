"""Pytest fixtures. Fully offline: stub backend, in-memory hash store."""

from __future__ import annotations

import pytest

import prooflens.config as config
from prooflens.engine import InMemoryHashStore
from prooflens.vision import get_backend


@pytest.fixture(autouse=True)
def _hermetic_vision_env(monkeypatch):
    """Never call a live vision provider from the suite, regardless of the
    developer's local .env (which may set VISION_BACKEND=groq to run the app).
    OS env vars take precedence over the .env file in pydantic-settings, so
    this pins the default backend to the stub and blanks every provider key.
    Tests that exercise live-AI paths pass an explicit backend / monkeypatch and
    are unaffected."""
    monkeypatch.setenv("VISION_BACKEND", "stub")
    for key in (
        "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
        "AIMLAPI_API_KEY", "NVIDIA_API_KEY",
    ):
        monkeypatch.setenv(key, "")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def stub_backend():
    return get_backend("stub")


@pytest.fixture
def hash_store():
    return InMemoryHashStore()
