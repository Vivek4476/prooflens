"""Generic OpenAI-compatible vision backend (stdlib only, no SDK required).

Works with any endpoint that speaks the OpenAI /chat/completions contract with
image_url content — Google Gemini (AI Studio), OpenRouter, Groq, a local
Ollama/vLLM, etc. Only the base URL, model and key differ; the rubric is the
same everywhere.
"""

from __future__ import annotations

import base64
import logging
import urllib.error  # noqa: F401 - keeps `urllib` bound so tests can patch openai_compat.urllib.request

from ._http import VisionUnavailable, post_chat  # VisionUnavailable re-exported for back-compat
from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json

logger = logging.getLogger("prooflens.vision")


class OpenAICompatBackend(VisionBackend):
    is_real = True

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        max_edge: int = 768,
        timeout: float = 30.0,
        temperature: float = 0.0,
    ):
        if not api_key:
            raise ValueError(f"an API key is required for the {name} backend")
        self.name = name
        self.api_key = api_key
        self.model = model
        self.invoke_url = base_url.rstrip("/") + "/chat/completions"
        self.max_edge = max_edge
        self.timeout = timeout
        # Deterministic by default: the same photo must yield the same assessment
        # (reproducibility — a fraud verdict that flips between calls is indefensible).
        self.temperature = temperature

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        jpeg = resize_for_model(image_bytes, self.max_edge)
        data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        payload = {
            "model": self.model,
            "max_tokens": 512,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
        }
        data, request_id = post_chat(
            invoke_url=self.invoke_url, api_key=self.api_key,
            payload=payload, timeout=self.timeout, name=self.name, model=self.model,
        )
        generation_id = data.get("id")
        logger.info(
            "vision inference OK backend=%s model=%s request_id=%s generation_id=%s",
            self.name, self.model, request_id, generation_id,
        )
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionUnavailable(
                f"{self.name} returned an unexpected response shape: {str(data)[:200]}"
            ) from exc
        raw = parse_model_json(text)
        return ContentAssessment(**raw, backend=self.name, model=self.model)
