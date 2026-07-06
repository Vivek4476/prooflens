"""Generic OpenAI-compatible vision backend (stdlib only, no SDK required).

Works with any endpoint that speaks the OpenAI /chat/completions contract with
image_url content — Google Gemini (AI Studio), OpenRouter, Groq, a local
Ollama/vLLM, etc. Only the base URL, model and key differ; the rubric is the
same everywhere.
"""

from __future__ import annotations

import base64
import json
import logging
import socket
import urllib.error
import urllib.request

from .base import VisionBackend, resize_for_model
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json

logger = logging.getLogger("prooflens.vision")


class VisionUnavailable(RuntimeError):
    """The vision provider could not be reached or returned an error.

    Carries the exact, actionable reason (HTTP status or transport failure) so
    the API can surface it instead of a generic "could not score" message.
    """

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


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
                # Some providers (e.g. AI/ML API) sit behind Cloudflare and block
                # the default "Python-urllib" agent with a 403/1010 bot signature.
                "User-Agent": "ProofLens/0.1 (+https://prooflens.app)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                request_id = resp.headers.get("x-request-id") or resp.headers.get("cf-ray")
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            req_id = exc.headers.get("x-request-id") if exc.headers else None
            logger.warning(
                "vision inference FAILED backend=%s model=%s http=%s request_id=%s detail=%s",
                self.name, self.model, exc.code, req_id, detail,
            )
            raise VisionUnavailable(
                f"{self.name} API error {exc.code}: {detail}", status=exc.code
            ) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            logger.warning(
                "vision inference FAILED backend=%s model=%s transport=%r",
                self.name, self.model, reason,
            )
            raise VisionUnavailable(
                f"{self.name} could not be reached (timeout/connection): {reason}"
            ) from exc

        # Req #6: log the model + a provider request id for every inference.
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
