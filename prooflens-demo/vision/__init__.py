"""Pluggable vision backends, selected by the VISION_BACKEND env var.

Usage:
    from vision import get_backend
    backend = get_backend()            # honours VISION_BACKEND (default "stub")
    verdict = backend.assess(img_bytes)

Or pick explicitly:
    backend = get_backend("anthropic")
"""

from __future__ import annotations

from typing import Optional

from config import VISION_BACKEND
from .base import VisionBackend, RUBRIC_FIELDS

# Names of every backend the demo knows about.
ALL_BACKENDS = ("stub", "anthropic", "gemini", "openai", "local")


def get_backend(name: Optional[str] = None) -> VisionBackend:
    """Construct a backend by name (defaults to VISION_BACKEND from config/env).

    Raises RuntimeError if the chosen backend's key/SDK is missing — except for
    "stub", which always works.
    """
    name = (name or VISION_BACKEND or "stub").strip().lower()

    if name == "stub":
        from .stub import StubBackend

        return StubBackend()
    if name == "anthropic":
        from .anthropic_backend import AnthropicBackend

        return AnthropicBackend()
    if name == "gemini":
        from .gemini_backend import GeminiBackend

        return GeminiBackend()
    if name == "openai":
        from .openai_backend import OpenAIBackend

        return OpenAIBackend()
    if name == "local":
        from .local_backend import LocalBackend

        return LocalBackend()

    raise RuntimeError(
        f"Unknown VISION_BACKEND '{name}'. Choose one of: {', '.join(ALL_BACKENDS)}."
    )


__all__ = ["get_backend", "VisionBackend", "ALL_BACKENDS", "RUBRIC_FIELDS"]
