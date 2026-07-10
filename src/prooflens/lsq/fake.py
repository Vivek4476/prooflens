"""FakeLSQClient — the in-memory LSQ used by all tests and local dev.

Records every custom-field write per opportunity, preserving write order, so a
test can assert the three fields were written as (band, score, reason). Makes no
network calls.
"""

from __future__ import annotations

import functools
import io

from .base import FieldUpdate

# Substring that marks a URL as "the fetch fails" — lets tests exercise the
# bulk service's fail-open path without a real (or even reachable) LSQ.
BAD_FETCH_MARKER = "__BADFETCH__"


@functools.lru_cache(maxsize=1)
def _scorable_image_bytes() -> bytes:
    """A small, synthetic-but-scorable JPEG: a noisy skin-tone-ish scene so the
    stub vision backend (and the golden checks: sharpness/uniqueness/recapture)
    treat it as a plausible photo rather than a flat graphic. Generated once,
    in-process — no test fixtures are reached from library code."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(1234)
    h, w = 256, 256
    # Base skin-like tone (passes the stub's crude skin-tone mask) plus noise
    # (keeps distinct-colour count high, i.e. not "flat graphic", and gives
    # sharpness/recapture something textured rather than a blank screen).
    base = np.array([180, 130, 100], dtype=np.int16)
    noise = rng.integers(-40, 40, size=(h, w, 3), endpoint=True)
    arr = np.clip(base + noise, 0, 255).astype("uint8")
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class FakeLSQClient:
    is_real = False

    def __init__(self) -> None:
        # opportunity_id -> ordered list of (field_id, value) as written
        self.writes: dict[str, list[tuple[str, str]]] = {}

    def update_custom_fields(self, opportunity_id: str, updates: list[FieldUpdate]) -> None:
        log = self.writes.setdefault(opportunity_id, [])
        for u in updates:
            log.append((u.field_id, u.value))

    def fetch_image(self, image_url: str) -> bytes:
        """Return scorable image bytes for any normal URL; raise if the URL
        contains BAD_FETCH_MARKER, so callers (the bulk service) can exercise
        their fail-open per-row error handling."""
        if BAD_FETCH_MARKER in image_url:
            raise RuntimeError(f"fake fetch failed for {image_url!r}")
        return _scorable_image_bytes()

    # --- test helpers ---
    def fields(self, opportunity_id: str) -> dict[str, str]:
        """Final value of each field for an opportunity."""
        return {fid: val for fid, val in self.writes.get(opportunity_id, [])}

    def order(self, opportunity_id: str) -> list[str]:
        """The field ids in the order they were written."""
        return [fid for fid, _ in self.writes.get(opportunity_id, [])]
