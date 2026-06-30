"""VisionBackend interface + shared rubric, prompt, resizing and normalisation.

Every backend answers the SAME rubric with the SAME prompt so results are
comparable across models in the bake-off. Each backend implements
`assess(image_bytes) -> dict` and returns a normalised verdict.
"""

from __future__ import annotations

import io
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict

from config import VISION_MAX_EDGE

# The structured fields every backend must return.
RUBRIC_FIELDS = (
    "people_count",
    "setting",
    "primary_subject",
    "people_present",
    "looks_like_photo_of_a_screen",
    "is_designed_graphic",
    "is_meme_or_screenshot",
    "meeting_plausibility",
    "reason",
)

# Identical instruction across all backends.
SYSTEM_PROMPT = (
    "You are ProofLens, a strict visual verifier for insurance-agent "
    '"proof-of-meeting" photos. A good proof photo shows a real, in-person '
    "meeting between people in a plausible setting (home, office, cafe). "
    "You must flag photos that are NOT genuine meeting evidence: photos taken "
    "of a screen/monitor, designed graphics or posters, memes or screenshots, "
    "stock-looking imagery, or scenes with no people. You judge the SCENE only "
    "— never identify individuals."
)

USER_PROMPT = (
    "Assess this image and respond with ONLY a JSON object (no prose, no "
    "markdown fences) with exactly these keys:\n"
    "  people_count: integer, number of distinct people visible\n"
    "  setting: short string, e.g. 'home living room', 'office', 'cafe', "
    "'street', 'unknown'\n"
    "  primary_subject: short string describing the main subject\n"
    "  people_present: boolean\n"
    "  looks_like_photo_of_a_screen: boolean (photographed monitor/phone/TV, "
    "moire, bezel, glare)\n"
    "  is_designed_graphic: boolean (poster, slide, ad, rendered graphic)\n"
    "  is_meme_or_screenshot: boolean\n"
    "  meeting_plausibility: integer 0-100, how plausibly this shows a real "
    "in-person meeting\n"
    "  reason: one short sentence explaining the score\n"
)


class VisionBackend(ABC):
    """Pluggable vision backend. Subclasses implement `assess`."""

    name: str = "base"
    is_real: bool = True  # False for the stub (so the UI can label it honestly)

    @abstractmethod
    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        """Return a normalised verdict dict with RUBRIC_FIELDS (+ backend, model)."""
        raise NotImplementedError


def resize_for_model(image_bytes: bytes, max_edge: int = VISION_MAX_EDGE) -> bytes:
    """Downscale so the long edge is <= max_edge, to cut tokens/latency.

    Returns JPEG bytes. If Pillow is unavailable or the image already fits, the
    original bytes are returned unchanged.
    """
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > max_edge:
            scale = max_edge / float(long_edge)
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:
        return image_bytes


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in {"true", "yes", "1", "y"}
    return False


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


def parse_model_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from a model's text response, robust to fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        # Otherwise grab the first {...} block.
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)


def normalize(raw: Dict[str, Any], *, backend: str, model: str) -> Dict[str, Any]:
    """Coerce a raw model dict into the canonical verdict shape."""
    plaus = _coerce_int(raw.get("meeting_plausibility"), 0)
    plaus = max(0, min(100, plaus))
    return {
        "people_count": _coerce_int(raw.get("people_count"), 0),
        "setting": str(raw.get("setting", "unknown"))[:120],
        "primary_subject": str(raw.get("primary_subject", "unknown"))[:120],
        "people_present": _coerce_bool(raw.get("people_present")),
        "looks_like_photo_of_a_screen": _coerce_bool(
            raw.get("looks_like_photo_of_a_screen")
        ),
        "is_designed_graphic": _coerce_bool(raw.get("is_designed_graphic")),
        "is_meme_or_screenshot": _coerce_bool(raw.get("is_meme_or_screenshot")),
        "meeting_plausibility": plaus,
        "reason": str(raw.get("reason", ""))[:300],
        "backend": backend,
        "model": model,
    }


def error_verdict(backend: str, model: str, message: str) -> Dict[str, Any]:
    """A safe, neutral verdict used when a backend call fails."""
    return {
        "people_count": 0,
        "setting": "unknown",
        "primary_subject": "unknown",
        "people_present": False,
        "looks_like_photo_of_a_screen": False,
        "is_designed_graphic": False,
        "is_meme_or_screenshot": False,
        "meeting_plausibility": 50,
        "reason": f"Vision backend error: {message}",
        "backend": backend,
        "model": model,
        "error": True,
    }
