"""VisionBackend protocol + shared image resizing.

A backend turns image bytes into a validated :class:`ContentAssessment` using
the shared rubric. ``assess`` may raise; the relevance check owns retry/fallback.
"""

from __future__ import annotations

import io
from typing import Protocol, runtime_checkable

from .schema import ContentAssessment


@runtime_checkable
class VisionBackend(Protocol):
    name: str
    is_real: bool  # False for the stub, so the UI/CLI can label it honestly

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        """Return a validated content assessment, or raise on failure."""
        ...


def resize_for_model(image_bytes: bytes, max_edge: int = 768) -> bytes:
    """Downscale so the long edge is <= max_edge (cuts tokens/latency).

    Returns JPEG bytes. If Pillow is unavailable or the image already fits, the
    original bytes are returned unchanged.
    """
    try:
        from PIL import Image
    except Exception:  # pragma: no cover
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > max_edge:
            scale = max_edge / float(long_edge)
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:  # pragma: no cover
        return image_bytes
