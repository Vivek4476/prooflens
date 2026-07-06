"""Uniqueness check — dHash vs the tenant-scoped hash store.

Computes an 8-byte difference hash and compares (Hamming distance) against
prior hashes for this tenant. Hamming <= dup_exact => exact duplicate (hard
gate); <= dup_near => near-duplicate (flag). Stores only the hash + trail,
never the image. The pipeline is responsible for remembering the hash AFTER
scoring so an image never matches itself.
"""

from __future__ import annotations

import io

from ..scoring_config import Thresholds
from ..types import CheckOutcome, HashStore

NAME = "uniqueness"

try:
    import imagehash  # type: ignore
    from PIL import Image  # type: ignore

    _HASH = True
except Exception:  # pragma: no cover
    _HASH = False


def compute_dhash(image_bytes: bytes) -> str | None:
    if not _HASH:  # pragma: no cover
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return str(imagehash.dhash(img))  # 16 hex chars = 8 bytes = 64-bit dHash
    except Exception:
        return None


def run(
    image_bytes: bytes,
    *,
    tenant_id: str,
    store: HashStore,
    thresholds: Thresholds,
) -> CheckOutcome:
    if not _HASH:  # pragma: no cover
        return CheckOutcome(NAME, available=False, score=None, summary="imagehash not installed.")

    dhash = compute_dhash(image_bytes)
    if dhash is None:
        return CheckOutcome(NAME, available=True, score=0.0, summary="Could not decode image.")

    match = store.nearest(tenant_id, dhash)
    data: dict = {
        "dhash": dhash,
        "distance": None,
        "exact_duplicate": False,
        "near_duplicate": False,
    }

    if match is None:
        return CheckOutcome(
            NAME,
            available=True,
            score=100.0,
            summary="First time this image has been seen for the tenant.",
            metric=None,
            data=data,
        )

    dist = match.distance
    data["distance"] = dist
    dup_exact = thresholds.dup_exact
    dup_near = thresholds.dup_near
    uniq = thresholds.unique_distance

    if dist <= dup_exact:
        data["exact_duplicate"] = True
        score, summary = 0.0, "Exact duplicate of an earlier upload."
    elif dist <= dup_near:
        data["near_duplicate"] = True
        score, summary = 20.0, "Near-duplicate of an earlier upload."
    elif dist >= uniq:
        score, summary = 100.0, "Comfortably different from anything seen before."
    else:
        score = (dist - dup_near) / (uniq - dup_near) * 100.0
        summary = "Somewhat similar to a previous upload."

    data["trail"] = {
        "rep_id": match.rep_id,
        "opportunity_id": match.opportunity_id,
        "created_at": match.created_at,
    }
    return CheckOutcome(
        NAME, available=True, score=round(score, 1), summary=summary, metric=float(dist), data=data
    )
