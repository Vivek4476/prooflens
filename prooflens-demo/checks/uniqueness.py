"""Uniqueness check — dHash compared against a local SQLite store.

We compute a difference hash (dHash) of the image and compare it (Hamming
distance) against every hash we've seen before. Small distance => duplicate.
We store only the hash + a fake lead/rep/time trail, never the image.
"""

from __future__ import annotations

import io

from config import THRESHOLDS
from .types import CheckResult
import store

try:
    from PIL import Image  # type: ignore
    import imagehash  # type: ignore

    HASH_AVAILABLE = True
except Exception:  # pragma: no cover
    HASH_AVAILABLE = False

NAME = "uniqueness"


def compute_dhash(image_bytes: bytes):
    """Return the dHash hex string, or None if deps/decoding fail."""
    if not HASH_AVAILABLE:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return str(imagehash.dhash(img))
    except Exception:
        return None


def run(image_bytes: bytes, *, remember: bool = True) -> CheckResult:
    if not HASH_AVAILABLE:
        return CheckResult(
            name=NAME,
            passed=True,
            score=60.0,
            reason="imagehash/Pillow not installed — uniqueness not measured.",
            detail="Install Pillow and imagehash to enable this check.",
            available=False,
        )

    phash = compute_dhash(image_bytes)
    if phash is None:
        return CheckResult(
            name=NAME,
            passed=False,
            score=0.0,
            reason="Could not decode image for hashing.",
            available=True,
        )

    match = store.nearest(phash)

    if match is None:
        result = CheckResult(
            name=NAME,
            passed=True,
            score=100.0,
            reason="First image we've seen — unique.",
            detail="No prior hashes in the local store.",
            metric=None,
        )
    else:
        dist = match.distance
        dup = THRESHOLDS.dup_distance
        uniq = THRESHOLDS.unique_distance
        if dist <= dup:
            score = 0.0
            passed = False
            reason = "Exact / near-duplicate of an earlier upload."
        elif dist >= uniq:
            score = 100.0
            passed = True
            reason = "Comfortably different from anything seen before."
        else:
            score = (dist - dup) / (uniq - dup) * 100.0
            passed = True
            reason = "Somewhat similar to a previous upload."
        result = CheckResult(
            name=NAME,
            passed=passed,
            score=round(score, 1),
            reason=reason,
            detail=(
                f"Closest hash distance = {dist} "
                f"(dup<= {dup}, unique>= {uniq}); "
                f"prior trail: lead={match.lead}, rep={match.rep}, at {match.created_at}."
            ),
            metric=float(dist),
        )

    if remember:
        store.remember(phash)

    return result
