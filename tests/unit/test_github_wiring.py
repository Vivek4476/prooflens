"""get_backend + Settings wire the GitHub Models backend (OpenAI-compatible)."""
from __future__ import annotations

from prooflens import config
from prooflens.vision import get_backend
from prooflens.vision.openai_compat import OpenAICompatBackend


def test_get_backend_builds_github():
    b = get_backend(
        "github",
        api_key="github_pat_x",
        model="openai/gpt-4o-mini",
        base_url="https://models.github.ai/inference",
    )
    assert isinstance(b, OpenAICompatBackend)
    assert b.name == "github"
    assert b.model == "openai/gpt-4o-mini"
    assert b.invoke_url == "https://models.github.ai/inference/chat/completions"


def test_settings_build_github(monkeypatch):
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", "github_pat_x")
    s = config.Settings(_env_file=None)
    b = s.build_vision_backend("github")
    assert isinstance(b, OpenAICompatBackend)
    assert b.name == "github"
    # defaults from config
    assert b.model == "openai/gpt-4o-mini"
    assert b.invoke_url == "https://models.github.ai/inference/chat/completions"


def test_github_defaults(monkeypatch):
    monkeypatch.delenv("GITHUB_MODEL", raising=False)
    monkeypatch.delenv("GITHUB_BASE_URL", raising=False)
    s = config.Settings(_env_file=None)
    assert s.github_model == "openai/gpt-4o-mini"
    assert s.github_base_url == "https://models.github.ai/inference"
