"""get_backend + Settings wire the hybrid from CF settings."""
from __future__ import annotations

from prooflens import config
from prooflens.vision import get_backend
from prooflens.vision.hybrid import HybridBackend


def test_get_backend_builds_hybrid():
    b = get_backend("hybrid", api_key="k", base_url="https://cf/ai/v1",
                    vision_model="scout-m", reasoner_model="reason-m")
    assert isinstance(b, HybridBackend)
    assert b.model == "scout-m+reason-m"


def test_settings_build_hybrid(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "cf-token")
    s = config.Settings()
    assert s.cf_base_url == "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/v1"
    b = s.build_vision_backend("hybrid")
    assert isinstance(b, HybridBackend)
