"""Stub vision backend — deterministic, no network, no keys, DEFAULT.

It answers the same rubric as the real backends, but derives its verdict from a
few cheap, honest pixel statistics (distinct-colour count + skin-tone fraction)
rather than a real model. This makes the app run out of the box and makes the
golden set — synthetic images crafted to be cleanly separable by these
statistics — reproducible offline in CI.

It is NOT a real judgement: ``is_real = False`` so every surface labels it.
"""

from __future__ import annotations

import io

from .base import VisionBackend
from .schema import ContentAssessment

# Tunables for the deterministic heuristics. Chosen so the golden synthetic
# images separate cleanly; real scenes are handled by the real backends.
_THUMB = 64                 # analyse a 64x64 thumbnail
_FLAT_COLOR_MAX = 24        # <= this many distinct (3-bit) colours => flat graphic
_SKIN_MIN_FRACTION = 0.015  # >= this fraction of skin-tone pixels => people present


class StubBackend(VisionBackend):
    name = "stub"
    is_real = False

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((_THUMB, _THUMB))
        arr = np.asarray(img, dtype=np.int32)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        total = arr.shape[0] * arr.shape[1]

        # Distinct colours at 3 bits/channel: flat graphics have very few.
        quant = (arr >> 5).reshape(-1, 3)
        distinct = np.unique(quant, axis=0).shape[0]

        # Permissive RGB skin-tone mask — a crude stand-in for "people present".
        mx = arr.max(axis=2)
        mn = arr.min(axis=2)
        skin_mask = (
            (r > 95) & (g > 40) & (b > 20)
            & ((mx - mn) > 15)
            & (np.abs(r - g) > 15)
            & (r > g) & (r > b)
        )
        skin_fraction = float(skin_mask.sum()) / total if total else 0.0

        graphic_like = distinct <= _FLAT_COLOR_MAX
        people_present = skin_fraction >= _SKIN_MIN_FRACTION

        if people_present:
            people_count = 1 if skin_fraction < 0.05 else 2 if skin_fraction < 0.12 else 3
        else:
            people_count = 0

        if graphic_like:
            plausibility = 12
            setting = "graphic"
            subject = "designed graphic or screenshot"
            description = "A designed graphic or screenshot, not a photograph of a live scene."
        elif people_present:
            plausibility = min(90, 65 + people_count * 8)
            setting = "indoor"
            subject = "people in a room"
            description = f"{people_count} person(s) in an indoor setting."
        else:
            plausibility = 22
            setting = "scene"
            subject = "scene with no people"
            description = "A scene with no people present."

        # The stub cannot read interaction, so it mirrors visit_context to
        # plausibility (a real capture of people is treated as having context);
        # genuine visit-context judgement comes from the real backends. This keeps
        # the synthetic golden set deterministic and stable across v1 -> v2.
        return ContentAssessment(
            people_count=people_count,
            # The stub cannot read interaction; treat >=2 people as interacting so
            # a genuine multi-person scene stays a valid meeting deterministically.
            people_interacting=people_count >= 2,
            setting=setting,
            environment=setting,
            primary_subject=subject,
            scene_description=description,
            emotional_tone="neutral" if people_present else "unclear",
            looks_like_photo_of_a_screen=False,  # real screen recapture is a separate check
            is_designed_graphic=graphic_like,
            is_meme_or_screenshot=graphic_like,
            plausibility=plausibility,
            visit_context=plausibility,
            context_confidence="high",
            reason="Deterministic stub verdict (not a real model judgement).",
            backend=self.name,
            model="stub",
        )
