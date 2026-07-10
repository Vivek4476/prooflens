"""FakeLSQClient — the in-memory LSQ used by all tests and local dev.

Records every custom-field write per opportunity, preserving write order, so a
test can assert the three fields were written as (band, score, reason). Makes no
network calls.
"""

from __future__ import annotations

import functools
import hashlib
import io

from .base import FieldUpdate

# Substring that marks a URL as "the fetch fails" — lets tests exercise the
# bulk service's fail-open path without a real (or even reachable) LSQ.
BAD_FETCH_MARKER = "__BADFETCH__"


@functools.lru_cache(maxsize=256)
def _scorable_image_bytes(seed: int = 1234) -> bytes:
    """A small, synthetic-but-scorable JPEG: a noisy skin-tone-ish scene so the
    stub vision backend (and the golden checks: sharpness/uniqueness/recapture)
    treat it as a plausible photo rather than a flat graphic. Generated once,
    in-process — no test fixtures are reached from library code."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    h, w = 256, 256
    yy, xx = np.mgrid[0:h, 0:w]
    # Base skin-like tone (passes the stub's crude skin-tone mask). The seed drives
    # LOW-frequency structure — a gradient + a large tinted block — so different URLs
    # get different perceptual hashes (else the recapture/uniqueness check dedups them
    # all as recycled). High-frequency noise keeps it textured, not a flat graphic.
    base = np.array([180, 130, 100], dtype=np.int16)
    arr = np.tile(base, (h, w, 1)).astype(np.int16)
    gx = rng.integers(-45, 45, size=3)
    gy = rng.integers(-45, 45, size=3)
    for c in range(3):
        arr[..., c] += ((xx / w) * gx[c] + (yy / h) * gy[c]).astype(np.int16)
    by, bx = int(rng.integers(0, h // 2)), int(rng.integers(0, w // 2))
    bh, bw = int(rng.integers(h // 4, h // 2)), int(rng.integers(w // 4, w // 2))
    arr[by : by + bh, bx : bx + bw] += rng.integers(-50, 50, size=3).astype(np.int16)
    arr += rng.integers(-18, 18, size=(h, w, 3), endpoint=True).astype(np.int16)
    arr = np.clip(arr, 0, 255).astype("uint8")
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
        # Deterministic-but-distinct per URL, so a bulk batch of different URLs
        # produces different images (varied scores) instead of all deduping as
        # recycled. Same URL always yields the same bytes.
        seed = int(hashlib.sha256(image_url.encode()).hexdigest()[:8], 16)
        return _scorable_image_bytes(seed)

    # --- test helpers ---
    def fields(self, opportunity_id: str) -> dict[str, str]:
        """Final value of each field for an opportunity."""
        return {fid: val for fid, val in self.writes.get(opportunity_id, [])}

    def order(self, opportunity_id: str) -> list[str]:
        """The field ids in the order they were written."""
        return [fid for fid, _ in self.writes.get(opportunity_id, [])]
