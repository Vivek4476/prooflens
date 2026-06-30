"""Person-presence check — OpenCV detection (detection only, no identity).

Uses OpenCV's HOG people detector plus a Haar face cascade as a fallback. We
only answer "is a human in frame at all?" — we never identify anyone and store
nothing about them.
"""

from __future__ import annotations

from ._imaging import CV2_AVAILABLE, load_cv2_bgr
from .types import CheckResult

NAME = "person_presence"


def _detect(img) -> int:
    """Return number of people/faces detected (best effort)."""
    import cv2  # available when CV2_AVAILABLE

    count = 0

    # 1) HOG full-body / pedestrian detector.
    try:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        # Downscale very large images for speed.
        h, w = img.shape[:2]
        scale = 1.0
        if max(h, w) > 960:
            scale = 960.0 / max(h, w)
            img_small = cv2.resize(img, (int(w * scale), int(h * scale)))
        else:
            img_small = img
        rects, _ = hog.detectMultiScale(
            img_small, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        count = max(count, len(rects))
    except Exception:
        pass

    # 2) Haar face cascade as a fallback (catches close-up selfies HOG misses).
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if not cascade.empty():
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            count = max(count, len(faces))
    except Exception:
        pass

    return count


def run(image_bytes: bytes) -> CheckResult:
    if not CV2_AVAILABLE:
        return CheckResult(
            name=NAME,
            passed=True,
            score=60.0,
            reason="OpenCV not installed — person detection skipped.",
            detail="Install opencv-python to enable this check.",
            available=False,
        )

    img = load_cv2_bgr(image_bytes)
    if img is None:
        return CheckResult(
            name=NAME,
            passed=False,
            score=0.0,
            reason="Could not decode image for person detection.",
            available=True,
        )

    n = _detect(img)
    if n > 0:
        return CheckResult(
            name=NAME,
            passed=True,
            score=100.0,
            reason=f"Detected {n} person/face region(s).",
            detail="Detection only — no identity, nothing stored.",
            metric=float(n),
        )
    return CheckResult(
        name=NAME,
        passed=False,
        score=20.0,
        reason="No person detected in frame.",
        detail="HOG + Haar found no people. Detection only, no identity.",
        metric=0.0,
    )
