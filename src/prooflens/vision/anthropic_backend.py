"""Anthropic vision backend (claude-haiku-4-5, official SDK).

NEVER called in tests or CI. Do not exercise this without explicit approval —
it spends money. The stub is the default everywhere else.
"""

from __future__ import annotations

import base64

from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json


class AnthropicBackend(VisionBackend):
    name = "anthropic"
    is_real = True

    def __init__(self, *, api_key: str, model: str = "claude-haiku-4-5", max_edge: int = 768):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the anthropic backend")
        self.model = model
        self.max_edge = max_edge
        # Imported lazily so the dependency is optional and never loaded in tests.
        import anthropic  # type: ignore

        self._client = anthropic.Anthropic(api_key=api_key)

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        jpeg = resize_for_model(image_bytes, self.max_edge)
        b64 = base64.standard_b64encode(jpeg).decode("ascii")
        resp = self._client.messages.create(
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
        text = "".join(block.text for block in resp.content if block.type == "text")
        raw = parse_model_json(text)
        return ContentAssessment(**raw, backend=self.name, model=self.model)
