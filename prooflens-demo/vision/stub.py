"""Stub vision backend — deterministic, no network, no keys.

Produces a stable fake verdict derived from the image bytes so the app runs out
of the box. The verdict is reproducible for the same image (hash of bytes) and
gently varied so the demo doesn't always look identical. It also peeks at a few
cheap pixel statistics (via Pillow, if present) to make screen-like/graphic-like
guesses feel a little less arbitrary — but it is NOT a real judgement and the UI
labels it as such.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any, Dict

from .base import VisionBackend, normalize


class StubBackend(VisionBackend):
    name = "stub"
    is_real = False

    def assess(self, image_bytes: bytes) -> Dict[str, Any]:
        digest = hashlib.sha256(image_bytes).digest()
        seed = digest[0]

        # Cheap, optional pixel heuristics to flavour the fake verdict.
        graphic_like = False
        try:
            from PIL import Image  # type: ignore

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            small = img.resize((16, 16))
            colors = small.getcolors(maxcolors=256) or []
            # Few distinct colors => poster/graphic-ish.
            graphic_like = len(colors) <= 12
        except Exception:
            pass

        people_count = seed % 4  # 0..3
        people_present = people_count > 0
        # Plausibility: more people => more plausible meeting; clamp to band.
        base = 35 + people_count * 18 + (seed % 13)
        plausibility = max(0, min(100, base))

        raw = {
            "people_count": people_count,
            "setting": ["home", "office", "cafe", "unknown"][seed % 4],
            "primary_subject": "people seated together" if people_present else "scene",
            "people_present": people_present,
            "looks_like_photo_of_a_screen": (seed % 7) == 0,
            "is_designed_graphic": graphic_like,
            "is_meme_or_screenshot": (seed % 11) == 0,
            "meeting_plausibility": plausibility,
            "reason": "STUB verdict (deterministic, not a real model judgement).",
        }
        return normalize(raw, backend=self.name, model="stub")
