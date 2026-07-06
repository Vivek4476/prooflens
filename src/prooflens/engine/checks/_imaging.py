"""Optional OpenCV/numpy decode helpers shared by the deterministic checks.

If cv2/numpy are missing, the loaders return None and the dependent checks
report themselves unavailable (neutral) instead of crashing — fail-open.
"""

from __future__ import annotations

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    CV2_AVAILABLE = True
except Exception:  # pragma: no cover
    CV2_AVAILABLE = False


def load_gray(image_bytes: bytes):
    if not CV2_AVAILABLE:
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


def load_bgr(image_bytes: bytes):
    if not CV2_AVAILABLE:
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


__all__ = ["CV2_AVAILABLE", "load_gray", "load_bgr"]
