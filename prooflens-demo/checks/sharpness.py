"""Sharpness check — OpenCV Laplacian variance.

A low variance of the Laplacian means few sharp edges => blurry image. We map
the variance onto a 0-100 score with a linear ramp between `blur_floor`
(fully blurred) and `sharp_ok` (clearly readable).
"""

from __future__ import annotations

from config import THRESHOLDS
from ._imaging import CV2_AVAILABLE, load_cv2_gray
from .types import CheckResult

NAME = "sharpness"


def run(image_bytes: bytes) -> CheckResult:
    if not CV2_AVAILABLE:
        return CheckResult(
            name=NAME,
            passed=True,
            score=60.0,
            reason="OpenCV not installed — sharpness not measured.",
            detail="Install opencv-python to enable this check.",
            available=False,
        )

    gray = load_cv2_gray(image_bytes)
    if gray is None:
        return CheckResult(
            name=NAME,
            passed=False,
            score=0.0,
            reason="Could not decode image for sharpness.",
            available=True,
        )

    import cv2  # local import; guaranteed available here

    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    floor = THRESHOLDS.blur_floor
    ok = THRESHOLDS.sharp_ok
    if variance <= floor:
        score = 0.0
    elif variance >= ok:
        score = 100.0
    else:
        score = (variance - floor) / (ok - floor) * 100.0

    passed = variance > floor
    if variance <= floor:
        reason = "Image looks fully blurred."
    elif variance < ok:
        reason = "Image is a little soft but readable."
    else:
        reason = "Image is sharp."

    return CheckResult(
        name=NAME,
        passed=passed,
        score=round(score, 1),
        reason=reason,
        detail=f"Laplacian variance = {variance:.1f} (floor {floor:.0f}, ok {ok:.0f}).",
        metric=round(variance, 1),
    )
