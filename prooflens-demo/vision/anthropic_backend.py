"""Anthropic (Claude Haiku 4.5) vision backend."""

from __future__ import annotations

import base64
import os
from typing import Any, Dict

from config import ANTHROPIC_MODEL
from .base import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    VisionBackend,
    error_verdict,
    normalize,
    parse_model_json,
    resize_for_model,
)


class AnthropicBackend(VisionBackend):
    name = "anthropic"

    def __init__(self) -> None:
        self.model = ANTHROPIC_MODEL
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        from anthropic import Anthropic  # imported lazily

        self.client = Anthropic()

    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            img = resize_for_model(image_bytes)
            b64 = base64.standard_b64encode(img).decode("ascii")
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    }
                ],
            )
            text = "".join(
                block.text for block in resp.content if getattr(block, "type", "") == "text"
            )
            raw = parse_model_json(text)
            return normalize(raw, backend=self.name, model=self.model)
        except Exception as exc:  # pragma: no cover - network path
            return error_verdict(self.name, self.model, str(exc))
