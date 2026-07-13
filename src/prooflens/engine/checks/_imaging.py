"""Optional OpenCV/numpy decode helpers shared by the deterministic checks.

If cv2/numpy are missing, the loaders return None and the dependent checks
report themselves unavailable (neutral) instead of crashing — fail-open.
"""

from __future__ import annotations

# Decompression-bomb bound. A genuine proof-of-visit phone photo is a few
# megapixels; anything past this is either a bomb or unusable. cv2.imdecode and
# PIL both decode the FULL raster into memory, so an unbounded image can OOM a
# small instance (ProofLens runs on a memory-constrained Render box). We reject
# by pixel count BEFORE the heavy decode.
MAX_IMAGE_PIXELS = 40_000_000  # 40 MP

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    CV2_AVAILABLE = True
except Exception:  # pragma: no cover
    CV2_AVAILABLE = False

try:
    from PIL import Image as _PILImage  # type: ignore

    # Make PIL raise DecompressionBombError on oversized rasters everywhere it
    # decodes (uniqueness/exif/resize_for_model already catch + fail-open).
    _PILImage.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover
    _PIL_AVAILABLE = False


def within_pixel_budget(image_bytes: bytes) -> bool:
    """Peek the image header (no full decode) and report whether it's within the
    pixel budget. An unreadable/unknown header returns True — let the real
    decoder handle it (it fails open to an unavailable check), we only want to
    stop the pathological megapixel case before cv2/PIL allocates the raster."""
    if not _PIL_AVAILABLE:
        return True
    import io

    try:
        with _PILImage.open(io.BytesIO(image_bytes)) as im:
            w, h = im.size
    except Exception:
        return True
    return w * h <= MAX_IMAGE_PIXELS


def load_gray(image_bytes: bytes):
    if not CV2_AVAILABLE or not within_pixel_budget(image_bytes):
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


def load_bgr(image_bytes: bytes):
    if not CV2_AVAILABLE or not within_pixel_budget(image_bytes):
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


__all__ = ["CV2_AVAILABLE", "MAX_IMAGE_PIXELS", "within_pixel_budget", "load_gray", "load_bgr"]
