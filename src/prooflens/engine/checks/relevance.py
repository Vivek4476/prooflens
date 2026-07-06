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
        return CheckOutcome(
            NAME,
            available=False,
            score=None,
            summary=f"Vision check unavailable: {last_error[:120]}",
            data={"error": True},
        )

    plaus = assessment.plausibility
    # The check's own contribution tracks plausibility, knocked down by red flags.
    score = float(plaus)
    if assessment.has_red_flag:
        score = min(score, 25.0)

    data = assessment.model_dump()
    data["is_real_backend"] = vision.is_real
    return CheckOutcome(
        NAME,
        available=True,
        score=round(score, 1),
        summary=(
            f"{assessment.people_count} person(s), setting={assessment.setting}, "
            f"plausibility={plaus}" + ("" if vision.is_real else " [STUB]")
        ),
        metric=float(plaus),
        data=data,
    )
