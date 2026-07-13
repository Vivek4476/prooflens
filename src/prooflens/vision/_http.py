"""Shared OpenAI-compatible /chat/completions POST (stdlib only).

Used by every hosted backend (Scout, reasoner, Groq, ...) so HTTP + error
semantics are identical: bot-safe User-Agent, HTTP status carried on
VisionUnavailable, transport errors mapped to the same exception.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger("prooflens.vision")


class VisionUnavailable(RuntimeError):
    """The vision provider could not be reached or returned an error.

    Carries the exact reason (HTTP status or transport failure) so the API can
    surface it instead of a generic message.
    """

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def post_chat(
    *, invoke_url: str, api_key: str, payload: dict, timeout: float, name: str, model: str
) -> tuple[dict, str | None]:
    """POST a chat-completions payload; return (parsed_json, request_id).

    Raises VisionUnavailable on any HTTP or transport failure.
    """
    req = urllib.request.Request(
        invoke_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Some providers sit behind Cloudflare and 403 the default urllib UA.
            "User-Agent": "ProofLens/0.1 (+https://prooflens.app)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            request_id = resp.headers.get("x-request-id") or resp.headers.get("cf-ray")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        req_id = exc.headers.get("x-request-id") if exc.headers else None
        logger.warning(
            "vision inference FAILED backend=%s model=%s http=%s request_id=%s detail=%s",
            name, model, exc.code, req_id, detail,
        )
        raise VisionUnavailable(f"{name} API error {exc.code}: {detail}", status=exc.code) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        logger.warning(
            "vision inference FAILED backend=%s model=%s transport=%r", name, model, reason
        )
        raise VisionUnavailable(
            f"{name} could not be reached (timeout/connection): {reason}"
        ) from exc
    return data, request_id
