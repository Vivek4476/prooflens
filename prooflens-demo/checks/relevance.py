"""Content / relevance check — the star. Wraps a pluggable vision backend.

Returns both a CheckResult (its 0-100 contribution) and the raw structured
verdict from the model, so the API can surface the full `vision` object.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from config import THRESHOLDS
from vision import get_backend
from vision.base import VisionBackend
from .types import CheckResult

NAME = "content_relevance"


def assess(
    image_bytes: bytes, backend: Optional[VisionBackend] = None
) -> Tuple[CheckResult, Dict[str, Any]]:
    backend = backend or get_backend()
    verdict = backend.assess(image_bytes)

    plaus = int(verdict.get("meeting_plausibility", 0))
    screen = bool(verdict.get("looks_like_photo_of_a_screen"))
    graphic = bool(verdict.get("is_designed_graphic"))
    meme = bool(verdict.get("is_meme_or_screenshot"))

    # The check's own score tracks plausibility, knocked down by red flags.
    score = float(plaus)
    if screen or graphic or meme:
        score = min(score, 25.0)

    passed = plaus >= THRESHOLDS.meeting_plausibility_gate and not (
        screen or graphic or meme
    )

    flags = []
    if screen:
        flags.append("photo of a screen")
    if graphic:
        flags.append("designed graphic")
    if meme:
        flags.append("meme/screenshot")

    if flags:
        reason = "Not genuine meeting evidence: " + ", ".join(flags) + "."
    elif plaus < THRESHOLDS.meeting_plausibility_gate:
        reason = f"Low meeting plausibility ({plaus}/100)."
    else:
        reason = verdict.get("reason") or f"Plausible meeting scene ({plaus}/100)."

    real_tag = "" if backend.is_real else " [STUB — not a real model judgement]"
    detail = (
        f"backend={verdict.get('backend')} model={verdict.get('model')} · "
        f"people={verdict.get('people_count')} · setting={verdict.get('setting')} · "
        f"plausibility={plaus}{real_tag}"
    )

    result = CheckResult(
        name=NAME,
        passed=passed,
        score=round(score, 1),
        reason=reason,
        detail=detail,
        available=True,
        metric=float(plaus),
    )
    return result, verdict
