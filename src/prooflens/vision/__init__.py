"""Vision backends: stub (default), anthropic, local_vlm — one rubric, many models."""

from __future__ import annotations

from .base import VisionBackend, resize_for_model
from .rubric import RUBRIC_VERSION
from .schema import ContentAssessment
from .stub import StubBackend

__all__ = [
    "VisionBackend",
    "ContentAssessment",
    "StubBackend",
    "RUBRIC_VERSION",
    "resize_for_model",
    "get_backend",
]


def get_backend(name: str = "stub", **kwargs) -> VisionBackend:
    """Construct a backend by name. Only ``stub`` has zero external deps.

    The real backends are imported lazily so their optional dependencies
    (anthropic / openai) are never required — or loaded — for the stub path.
    """
    name = (name or "stub").strip().lower()
    if name == "stub":
        return StubBackend()
    if name == "anthropic":
        from .anthropic_backend import AnthropicBackend

        return AnthropicBackend(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "claude-haiku-4-5"),
            max_edge=kwargs.get("max_edge", 768),
        )
    if name == "local_vlm":
        from .local_vlm import LocalVLMBackend

        return LocalVLMBackend(
            base_url=kwargs["base_url"],
            model=kwargs["model"],
            api_key=kwargs.get("api_key", "not-needed"),
            max_edge=kwargs.get("max_edge", 768),
        )
    raise ValueError(f"unknown vision backend: {name!r}")
