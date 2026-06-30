"""Metadata check — EXIF presence via Pillow, as a backstop.

EXIF (camera make/model, capture time, orientation) is weak evidence: it's
trivially stripped or faked, and many legitimate uploads lose it on the way
through chat apps. So this is a low-weight backstop, not a gate. We only report
presence and a few non-identifying fields.
"""

from __future__ import annotations

import io

from .types import CheckResult

try:
    from PIL import Image, ExifTags  # type: ignore

    PIL_AVAILABLE = True
except Exception:  # pragma: no cover
    PIL_AVAILABLE = False

NAME = "metadata"

# Non-identifying EXIF tags we're happy to surface.
_INTERESTING = {"Make", "Model", "DateTimeOriginal", "DateTime", "Software"}


def run(image_bytes: bytes) -> CheckResult:
    if not PIL_AVAILABLE:
        return CheckResult(
            name=NAME,
            passed=True,
            score=50.0,
            reason="Pillow not installed — EXIF not read.",
            detail="Install Pillow to enable this check.",
            available=False,
        )

    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
    except Exception:
        return CheckResult(
            name=NAME,
            passed=False,
            score=30.0,
            reason="Could not read image metadata.",
            available=True,
        )

    if not exif:
        return CheckResult(
            name=NAME,
            passed=False,
            score=40.0,
            reason="No EXIF metadata present.",
            detail="Often stripped by chat apps — weak signal, treated as a backstop.",
            metric=0.0,
        )

    tag_names = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
    found = {k: tag_names[k] for k in _INTERESTING if k in tag_names}
    detail_bits = ", ".join(f"{k}={v}" for k, v in found.items()) or "EXIF present."

    return CheckResult(
        name=NAME,
        passed=True,
        score=85.0,
        reason="EXIF metadata present.",
        detail=detail_bits,
        metric=float(len(exif)),
    )
