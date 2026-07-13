"""The default vision backend is the hybrid; stub is only reachable by name."""
from __future__ import annotations

from prooflens import config


def test_default_backend_is_hybrid(monkeypatch):
    monkeypatch.delenv("VISION_BACKEND", raising=False)
    assert config.Settings(_env_file=None).vision_backend == "hybrid"
