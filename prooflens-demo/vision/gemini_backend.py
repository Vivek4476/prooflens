"""Google Gemini (Flash / Flash-Lite) vision backend using the google-genai SDK."""

from __future__ import annotations

import os
from typing import Any, Dict

from config import GEMINI_MODEL
from .base import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    VisionBackend,
    error_verdict,
    normalize,
    parse_model_json,
    resize_for_model,
)


class GeminiBackend(VisionBackend):
    name = "gemini"

    def __init__(self) -> None:
        self.model = GEMINI_MODEL
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set.")
        from google import genai  # lazy import

        self.genai = genai
        self.client = genai.Client(api_key=api_key)

    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            from google.genai import types  # lazy import

            img = resize_for_model(image_bytes)
            resp = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=img, mime_type="image/jpeg"),
                    SYSTEM_PROMPT + "\n\n" + USER_PROMPT,
                ],
            )
            text = resp.text or ""
            raw = parse_model_json(text)
            return normalize(raw, backend=self.name, model=self.model)
        except Exception as exc:  # pragma: no cover - network path
            return error_verdict(self.name, self.model, str(exc))
