"""Local VLM backend — any OpenAI-compatible endpoint (Ollama, vLLM, ...).

Base URL + model come from env/config. NEVER called in tests or CI. Same rubric
as every other backend.
"""

from __future__ import annotations

import base64

from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json


class LocalVLMBackend(VisionBackend):
    name = "local_vlm"
    is_real = True

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        max_edge: int = 768,
    ):
        self.model = model
        self.max_edge = max_edge
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        jpeg = resize_for_model(image_bytes, self.max_edge)
        b64 = base64.standard_b64encode(jpeg).decode("ascii")
        data_uri = f"data:image/jpeg;base64,{b64}"
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=400,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
        )
        text = resp.choices[0].message.content or ""
        raw = parse_model_json(text)
        return ContentAssessment(**raw, backend=self.name, model=self.model)
