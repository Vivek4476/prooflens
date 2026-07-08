"""A VisionBackend that is deliberately unavailable.

Used when the configured default backend cannot be constructed (e.g. no API
key). Its assess() raises, so engine/checks/relevance.py records
available=False and fusion caps the verdict to Doubtful — the app degrades to
review instead of 503-ing or silently falling back to the stub.
"""

from __future__ import annotations

from .schema import ContentAssessment


class UnavailableVision:
    name = "unavailable"
    is_real = False

    def __init__(self, reason: str) -> None:
        self._reason = reason or "vision backend unavailable"

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        raise RuntimeError(self._reason)
