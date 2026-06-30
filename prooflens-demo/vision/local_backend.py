"""Local OpenAI-compatible vision backend (Ollama / vLLM serving an open model).

Points the OpenAI client at LOCAL_BASE_URL with LOCAL_MODEL (e.g. Qwen2-VL-2B
or Moondream). Most local servers ignore the API key, but the SDK requires one,
so LOCAL_API_KEY defaults to a placeholder.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from config import LOCAL_API_KEY, LOCAL_BASE_URL, LOCAL_MODEL
from .base import error_verdict, normalize, parse_model_json
from .openai_backend import OpenAIBackend, _chat_vision


class LocalBackend(OpenAIBackend):
    name = "local"

    def __init__(self) -> None:
        # Ensure the OpenAI client can construct even when no real key exists.
        os.environ.setdefault("LOCAL_API_KEY", LOCAL_API_KEY)
        self.model = LOCAL_MODEL
        from openai import OpenAI  # lazy import

        self.client = OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_BASE_URL)

    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            resp = _chat_vision(self.client, self.model, image_bytes)
            text = resp.choices[0].message.content or ""
            raw = parse_model_json(text)
            return normalize(raw, backend=self.name, model=self.model)
        except Exception as exc:  # pragma: no cover - network path
            return error_verdict(self.name, self.model, str(exc))
