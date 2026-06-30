"""OpenAI (mini vision model) backend, using the OpenAI Python SDK.

Also reused by the `local` backend, which points the same OpenAI-compatible
client at a self-hosted endpoint (Ollama / vLLM).
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

from config import OPENAI_MODEL
from .base import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    VisionBackend,
    error_verdict,
    normalize,
    parse_model_json,
    resize_for_model,
)


def _chat_vision(client, model: str, image_bytes: bytes) -> Dict[str, Any]:
    img = resize_for_model(image_bytes)
    b64 = base64.standard_b64encode(img).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"
    resp = client.chat.completions.create(
        model=model,
        max_tokens=400,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    )
    return resp


class OpenAIBackend(VisionBackend):
    name = "openai"

    def __init__(self, *, base_url: Optional[str] = None, model: Optional[str] = None,
                 api_key_env: str = "OPENAI_API_KEY") -> None:
        self.model = model or OPENAI_MODEL
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} is not set.")
        from openai import OpenAI  # lazy import

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            resp = _chat_vision(self.client, self.model, image_bytes)
            text = resp.choices[0].message.content or ""
            raw = parse_model_json(text)
            return normalize(raw, backend=self.name, model=self.model)
        except Exception as exc:  # pragma: no cover - network path
            return error_verdict(self.name, self.model, str(exc))
