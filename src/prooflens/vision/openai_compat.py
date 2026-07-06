"""Generic OpenAI-compatible vision backend (stdlib only, no SDK required).

Works with any endpoint that speaks the OpenAI /chat/completions contract with
image_url content — Google Gemini (AI Studio), OpenRouter, Groq, a local
Ollama/vLLM, etc. Only the base URL, model and key differ; the rubric is the
same everywhere.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json


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
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ValueError(f"an API key is required for the {name} backend")
        self.name = name
        self.api_key = api_key
        self.model = model
        self.invoke_url = base_url.rstrip("/") + "/chat/completions"
        self.max_edge = max_edge
        self.timeout = timeout

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        jpeg = resize_for_model(image_bytes, self.max_edge)
        data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        payload = {
            "model": self.model,
            "max_tokens": 512,
            "temperature": 0.2,
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
        req = urllib.request.Request(
            self.invoke_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"{self.name} API error {exc.code}: {detail}") from exc

        text = data["choices"][0]["message"]["content"] or ""
        raw = parse_model_json(text)
        return ContentAssessment(**raw, backend=self.name, model=self.model)
