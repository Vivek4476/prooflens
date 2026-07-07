"""Content / relevance check — the star. Wraps a pluggable vision backend.

Environment-invariant: asks "real people in a real captured scene vs
screen/graphic/meme/screenshot/object", never "does this look like an ideal
meeting". Malformed/failed model output is retried ONCE, then the pipeline
scores WITHOUT this check and records that in the breakdown (available=False).
"""

from __future__ import annotations

from ...vision.base import VisionBackend
from ..scoring_config import Thresholds
from ..types import CheckOutcome

NAME = "content"


def run(image_bytes: bytes, *, vision: VisionBackend, thresholds: Thresholds) -> CheckOutcome:
    assessment = None
    last_error = ""
    for _ in range(2):  # one try + one retry
        try:
            assessment = vision.assess(image_bytes)
            break
        except Exception as exc:  # pydantic validation / transport / parse errors
            last_error = str(exc)
            assessment = None

    if assessment is None:
        # Score WITHOUT this check; fusion will surface "scored without content analysis".
        # Keep the FULL provider error in data so the API can surface the exact
        # reason (401/402/429/timeout/…) when Live AI was explicitly requested.
        return CheckOutcome(
            NAME,
            available=False,
            score=None,
            summary=f"Vision check unavailable: {last_error[:120]}",
            data={"error": True, "detail": last_error},
        )

    plaus = assessment.plausibility
    # Two axes: capture authenticity (plausibility) and visit context. The check's
    # soft contribution blends them so a real photo that lacks any visit/interaction
    # is knocked down; a missing visit_context (older backend) falls back to
    # plausibility so it is never unfairly penalised. Red flags cap it hard.
    vc = assessment.visit_context if assessment.visit_context is not None else plaus
    score = 0.6 * float(plaus) + 0.4 * float(vc)
    if assessment.has_red_flag:
        score = min(score, 25.0)

    data = assessment.model_dump()
    data["is_real_backend"] = vision.is_real
    # Prefer the model's scene description — "what is in the picture" — falling back
    # to the structured summary when a backend doesn't provide one.
    summary = assessment.scene_description.strip() or (
        f"{assessment.people_count} person(s), setting={assessment.setting}"
    )
    if not vision.is_real:
        summary += " [STUB]"
    return CheckOutcome(
        NAME,
        available=True,
        score=round(score, 1),
        summary=summary,
        metric=float(plaus),
        data=data,
    )
