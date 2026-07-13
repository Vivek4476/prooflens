"""Two-stage vision backend: Scout (perception) + Reasoner (judgment).

Implements VisionBackend. Stage 1 produces a full ContentAssessment; Stage 2
refines the judgment fields. Fail-open: a Stage-2 failure keeps Scout's own
judgment (never worse than single-Scout); a Stage-1 failure propagates as
VisionUnavailable (the existing Unassessed path).
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from ._http import VisionUnavailable
from .base import VisionBackend
from .openai_compat import OpenAICompatBackend
from .reasoner import Reasoner
from .schema import ContentAssessment

logger = logging.getLogger("prooflens.vision")


class HybridBackend(VisionBackend):
    is_real = True

    def __init__(
        self, *, name: str = "hybrid", api_key: str, base_url: str,
        vision_model: str, reasoner_model: str,
        max_edge: int = 768, timeout: float = 30.0,
    ):
        self.name = name
        self.scout = OpenAICompatBackend(
            name="scout", api_key=api_key, model=vision_model,
            base_url=base_url, max_edge=max_edge, timeout=timeout,
        )
        self.reasoner = Reasoner(
            api_key=api_key, model=reasoner_model, base_url=base_url, timeout=timeout,
        )
        self.model = f"{vision_model}+{reasoner_model}"

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        # Stage 1 — perception (+ Scout's own judgment). Raises → Stage-1 fail-open.
        perception = self.scout.assess(image_bytes)
        try:
            judgment = self.reasoner.refine(perception)
        except (VisionUnavailable, ValidationError, ValueError) as exc:
            logger.warning("hybrid degraded=scout-only reason=%r", exc)
            return perception.model_copy(update={
                "backend": self.name,
                "model": f"{self.scout.model} (reasoner-unavailable)",
            })
        logger.info("hybrid OK degraded=false model=%s", self.model)
        return perception.model_copy(update={
            "plausibility": judgment.plausibility,
            "visit_context": judgment.visit_context,
            "context_confidence": judgment.context_confidence,
            "reason": judgment.reason,
            "backend": self.name,
            "model": self.model,
        })
