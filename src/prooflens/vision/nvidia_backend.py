"""NVIDIA-hosted VLM backend (e.g. meta/llama-3.2-90b-vision-instruct).

NVIDIA's free hosted endpoint (build.nvidia.com / integrate.api.nvidia.com) is
OpenAI-ish but the vision models take the image as an embedded
``<img src="data:image/jpeg;base64,..." />`` tag inside the message content —
NOT the OpenAI ``image_url`` array — with a ~180 KB base64 inline limit. So this
is its own backend, using only the standard library (no extra deps), so it works
straight from the CLI.

Get a free API key at https://build.nvidia.com (key looks like ``nvapi-...``).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json

_B64_INLINE_LIMIT = 180_000  # NVIDIA inline-image base64 length cap


class NvidiaBackend(VisionBackend):
    name = "nvidia"
    is_real = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta/llama-3.2-90b-vision-instruct",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        max_edge: int = 768,
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is required for the nvidia backend")
        self.api_key = api_key
        self.model = model
        self.invoke_url = base_url.rstrip("/") + "/chat/completions"
        self.max_edge = max_edge
        self.timeout = timeout

    def _image_b64(self, image_bytes: bytes) -> str:
        """Resize until the base64 fits NVIDIA's inline limit."""
        edge = self.max_edge
        b64 = ""
        for _ in range(4):
            jpeg = resize_for_model(image_bytes, edge)
            b64 = base64.b64encode(jpeg).decode("ascii")
            if len(b64) < _B64_INLINE_LIMIT:
                return b64
            edge = int(edge * 0.75)
        return b64  # last attempt; NVIDIA will report if it's still too large

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        b64 = self._image_b64(image_bytes)
        # Fold system + user prompt into one turn (most compatible) and append the
        # image tag NVIDIA's vision models expect.
        content = (
            f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}\n"
            f'<img src="data:image/jpeg;base64,{b64}" />'
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 512,
            "temperature": 0.2,
            "top_p": 1.0,
            "stream": False,
        }
        req = urllib.request.Request(
            self.invoke_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"NVIDIA API error {exc.code}: {detail}") from exc

        text = data["choices"][0]["message"]["content"]
        raw = parse_model_json(text)
        return ContentAssessment(**raw, backend=self.name, model=self.model)
