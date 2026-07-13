"""Stage 2 of the hybrid backend: reason over a perception (no image).

Takes a ContentAssessment's perceptual fields, asks a strong text model to
judge authenticity + visit-context, and returns a validated Judgment.
"""
from __future__ import annotations

import json
import logging

from ._http import VisionUnavailable, post_chat
from .rubric import REASONER_SYSTEM_PROMPT, REASONER_USER_TEMPLATE, REASONER_VERSION
from .schema import ContentAssessment, Judgment, parse_model_json

logger = logging.getLogger("prooflens.vision")

# The perceptual fields handed to the reasoner (NOT the judgment fields, which it
# produces, nor provenance).
PERCEPTION_FIELDS = (
    "people_count", "people_interacting", "setting", "environment",
    "primary_subject", "scene_description", "emotional_tone",
    "looks_like_photo_of_a_screen", "is_designed_graphic", "is_meme_or_screenshot",
)


class Reasoner:
    def __init__(
        self, *, api_key: str, model: str, base_url: str,
        timeout: float = 30.0, temperature: float = 0.0,
    ):
        if not api_key:
            raise ValueError("an API key is required for the reasoner")
        self.api_key = api_key
        self.model = model
        self.invoke_url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.temperature = temperature
        self.version = REASONER_VERSION

    def refine(self, perception: ContentAssessment) -> Judgment:
        p = {k: getattr(perception, k) for k in PERCEPTION_FIELDS}
        user = REASONER_USER_TEMPLATE.replace(
            "{perception}", json.dumps(p, ensure_ascii=False)
        )
        payload = {
            "model": self.model,
            "max_tokens": 300,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": REASONER_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        }
        data, request_id = post_chat(
            invoke_url=self.invoke_url, api_key=self.api_key,
            payload=payload, timeout=self.timeout, name="reasoner", model=self.model,
        )
        logger.info("reasoner OK model=%s request_id=%s", self.model, request_id)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionUnavailable(
                f"reasoner returned an unexpected shape: {str(data)[:200]}"
            ) from exc
        raw = parse_model_json(text)     # may raise ValueError (bad JSON)
        return Judgment(**raw)           # may raise ValidationError
