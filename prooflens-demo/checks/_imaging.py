"""Image decoding helpers shared by the deterministic checks.

OpenCV is optional: if it (or numpy) is missing, `load_cv2_gray` returns None
and the dependent checks report themselves as unavailable instead of crashing.
"""

from __future__ import annotations

from typing import Optional

try:
    import numpy as np  # type: ignore
    import cv2  # type: ignore

    CV2_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when cv2 absent
    CV2_AVAILABLE = False


def load_cv2_bgr(image_bytes: bytes):
    """Decode bytes into an OpenCV BGR image, or None if unavailable/undecodable."""
    if not CV2_AVAILABLE:
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def load_cv2_gray(image_bytes: bytes):
    """Decode bytes into a grayscale OpenCV image, or None."""
    if not CV2_AVAILABLE:
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    return img
