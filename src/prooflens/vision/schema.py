"""Structured, validated output of the content (vision) check.

Every backend returns a :class:`ContentAssessment`. Model output is parsed and
pydantic-validated; malformed output is a validation error the caller handles by
retrying once, then scoring WITHOUT this check.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ContentAssessment(BaseModel):
    """The rubric's output contract. Field names mirror rubrics/v1.yaml."""

    people_count: int = Field(ge=0, le=100)
    setting: str = "unknown"
    primary_subject: str = "unknown"
    looks_like_photo_of_a_screen: bool = False
    is_designed_graphic: bool = False
    is_meme_or_screenshot: bool = False
    plausibility: int = Field(ge=0, le=100)
    reason: str = ""

    # Backend provenance — not part of the rubric, filled in by the backend.
    backend: str = "unknown"
    model: str = "unknown"

    @field_validator("setting", "primary_subject", "reason", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return "" if v is None else str(v)[:300]

    @field_validator(
        "looks_like_photo_of_a_screen",
        "is_designed_graphic",
        "is_meme_or_screenshot",
        mode="before",
    )
    @classmethod
    def _coerce_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in {"true", "yes", "1", "y"}
        return bool(v)

    @field_validator("people_count", "plausibility", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> int:
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return 0

    @property
    def has_red_flag(self) -> bool:
        return (
            self.looks_like_photo_of_a_screen
            or self.is_designed_graphic
            or self.is_meme_or_screenshot
        )


def parse_model_json(text: str) -> dict:
    """Extract a JSON object from a model's text response, robust to code fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)
