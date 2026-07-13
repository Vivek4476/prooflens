"""The default vision backend is the hybrid; stub is only reachable by name."""
from __future__ import annotations

from prooflens import config


def test_default_backend_is_hybrid(monkeypatch):
    for var in ("VISION_BACKEND",):
        monkeypatch.delenv(var, raising=False)
    assert config.Settings().vision_backend == "hybrid"
