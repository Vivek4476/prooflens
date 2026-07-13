"""Vision backends: stub (default), anthropic, local_vlm — one rubric, many models."""

from __future__ import annotations

from .base import VisionBackend, resize_for_model
from .rubric import RUBRIC_VERSION
from .schema import ContentAssessment
from .stub import StubBackend
from .unavailable import UnavailableVision  # noqa: F401

__all__ = [
    "VisionBackend",
    "ContentAssessment",
    "StubBackend",
    "UnavailableVision",
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
    # OpenAI-compatible hosted/local endpoints (Gemini, OpenRouter, Groq, Cloudflare, ...).
    if name in ("local_vlm", "gemini", "openrouter", "aimlapi", "groq", "cloudflare"):
        from .openai_compat import OpenAICompatBackend

        return OpenAICompatBackend(
            name=name,
            api_key=kwargs.get("api_key", "not-needed"),
            model=kwargs["model"],
            base_url=kwargs["base_url"],
            max_edge=kwargs.get("max_edge", 768),
        )
    if name == "hybrid":
        from .hybrid import HybridBackend

        return HybridBackend(
            api_key=kwargs["api_key"],
            base_url=kwargs["base_url"],
            vision_model=kwargs["vision_model"],
            reasoner_model=kwargs["reasoner_model"],
            max_edge=kwargs.get("max_edge", 768),
        )
    if name == "nvidia":
        from .nvidia_backend import NvidiaBackend

        return NvidiaBackend(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "meta/llama-3.2-90b-vision-instruct"),
            base_url=kwargs.get("base_url", "https://integrate.api.nvidia.com/v1"),
            max_edge=kwargs.get("max_edge", 768),
        )
    raise ValueError(f"unknown vision backend: {name!r}")
