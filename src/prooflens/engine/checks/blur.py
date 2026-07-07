"""Sharpness check — OpenCV Laplacian variance.

Low variance => few sharp edges => blurred. Unreadable images get a quality
flag ("retake"), which the fusion layer treats as a weak signal — never a heavy
score penalty on its own. Maps variance onto 0-100 with a linear ramp between
``blur_floor`` (unreadable) and ``sharp_ok`` (clearly readable).
"""

from __future__ import annotations

from ..scoring_config import Thresholds
from ..types import CheckOutcome
from ._imaging import CV2_AVAILABLE, load_gray

NAME = "sharpness"


def run(image_bytes: bytes, thresholds: Thresholds) -> CheckOutcome:
    """Decode the grayscale then score it. The pipeline decodes once and calls
    ``run_on_gray`` directly; this wrapper stays for standalone/test callers."""
    if not CV2_AVAILABLE:  # pragma: no cover
        return CheckOutcome(NAME, available=False, score=None, summary="OpenCV not installed.")
    return run_on_gray(load_gray(image_bytes), thresholds)


def run_on_gray(gray, thresholds: Thresholds) -> CheckOutcome:
    if not CV2_AVAILABLE:  # pragma: no cover
        return CheckOutcome(NAME, available=False, score=None, summary="OpenCV not installed.")
    if gray is None:
        return CheckOutcome(NAME, available=True, score=0.0, summary="Could not decode image.")

    import cv2  # available here
    import numpy as np

    # CV_32F (not CV_64F) halves the full-resolution Laplacian array; the kernel
    # yields small integer responses that are exact in float32, so computing the
    # variance in float64 (var(dtype=...)) keeps the metric bit-identical.
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    variance = float(lap.var(dtype=np.float64))
    del lap
    floor, ok = thresholds.blur_floor, thresholds.sharp_ok

    if variance <= floor:
        score, summary = 0.0, "Unreadable — image is too blurred."
    elif variance >= ok:
        score, summary = 100.0, "Image is sharp."
    else:
        score = (variance - floor) / (ok - floor) * 100.0
        summary = "Slightly soft but readable."

    return CheckOutcome(
        NAME,
        available=True,
        score=round(score, 1),
        summary=summary,
        metric=round(variance, 1),
        data={"too_blurred": variance <= floor},
    )
