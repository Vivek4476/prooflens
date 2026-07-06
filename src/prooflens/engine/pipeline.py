"""The scoring pipeline — cheap → costly, free gates short-circuit the paid call.

Order:
  1. EXIF        (soft bonus, never gates)
  2. Sharpness   (quality flag)
  3. Uniqueness  (dHash vs tenant store; exact dup is a hard gate)
  4. Recapture   (moire/glare/bezel; "photo of a screen" is a hard gate)
  5. Content     (vision model) — SKIPPED if a free hard gate already fired,
                 so we never spend on the paid call for an obvious reject.
  6. Fusion.

Pure: no HTTP/queue/LSQ imports. The vision backend and hash store are injected
via EngineContext.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from ..vision.rubric import RUBRIC_VERSION
from .checks import blur, exif, recapture, relevance, uniqueness
from .fusion import fuse
from .types import CheckOutcome, EngineContext, Verdict


def _timed(fn: Callable[[], CheckOutcome]) -> CheckOutcome:
    """Run a check and stamp its wall-clock latency (for the /metrics histogram)."""
    start = time.perf_counter()
    out = fn()
    out.latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return out


def _free_hard_gate_fired(outcomes: list[CheckOutcome]) -> bool:
    """True if a free (non-vision) check already forces a reject, so we can skip
    the paid content call. Fail-open: only the unambiguous gates short-circuit."""
    by_name = {c.name: c for c in outcomes}
    uniq = by_name.get("uniqueness")
    if uniq and uniq.available and uniq.data.get("exact_duplicate"):
        return True
    recap = by_name.get("recapture")
    if recap and recap.available and recap.data.get("screen_detected"):
        return True
    return False


def score(image_bytes: bytes, context: EngineContext) -> Verdict:
    """Score one image. ``engine.score(image_bytes, context) -> Verdict``."""
    cfg = context.scoring
    outcomes: list[CheckOutcome] = [
        _timed(lambda: exif.run(image_bytes)),
        _timed(lambda: blur.run(image_bytes, cfg.thresholds)),
        _timed(lambda: uniqueness.run(
            image_bytes,
            tenant_id=context.tenant_id,
            store=context.hash_store,
            thresholds=cfg.thresholds,
        )),
        _timed(lambda: recapture.run(image_bytes)),
    ]

    # 5. Content — skip the paid vision call if a free hard gate already fired.
    if _free_hard_gate_fired(outcomes):
        outcomes.append(
            CheckOutcome(
                relevance.NAME,
                available=False,
                score=None,
                summary="Skipped — a free hard gate already rejected the image.",
                data={"skipped": True},
            )
        )
    else:
        outcomes.append(
            _timed(
                lambda: relevance.run(
                    image_bytes, vision=context.vision, thresholds=cfg.thresholds
                )
            )
        )

    result = fuse(outcomes, cfg)

    # Remember this image's hash AFTER scoring (so it never matches itself).
    if context.remember_hash:
        uniq = next((c for c in outcomes if c.name == uniqueness.NAME), None)
        dhash = uniq.data.get("dhash") if uniq else None
        if dhash:
            context.hash_store.remember(
                context.tenant_id,
                dhash,
                rep_id=context.rep_id,
                opportunity_id=context.opportunity_id,
                captured_at=context.captured_at,
            )

    return Verdict(
        score=result.score,
        band=result.band,
        reason=result.reason,
        reason_code=result.reason_code,
        checks=outcomes,
        rubric_version=RUBRIC_VERSION,
    )
