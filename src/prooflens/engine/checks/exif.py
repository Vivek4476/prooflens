"""EXIF check — timestamp/GPS presence via Pillow.

SOFT bonus signals only. EXIF is trivially stripped (chat apps) and device
clocks/GPS are user-controllable, so this NEVER gates a verdict — it only nudges
the blend slightly. We surface presence and a few non-identifying fields; we do
NOT treat GPS as ground truth.
"""

from __future__ import annotations

import io

from ..types import CheckOutcome

NAME = "exif"

try:
    from PIL import ExifTags, Image  # type: ignore

    _PIL = True
except Exception:  # pragma: no cover
    _PIL = False

# GPS IFD tag id in the top-level EXIF.
_GPS_IFD = 0x8825
_TIME_TAGS = {"DateTimeOriginal", "DateTime", "DateTimeDigitized"}


def run(image_bytes: bytes) -> CheckOutcome:
    if not _PIL:  # pragma: no cover
        return CheckOutcome(NAME, available=False, score=None, summary="Pillow not installed.")

    try:
        exif = Image.open(io.BytesIO(image_bytes)).getexif()
    except Exception:
        return CheckOutcome(NAME, available=True, score=50.0, summary="Could not read EXIF.")

    if not exif:
        return CheckOutcome(
            NAME,
            available=True,
            score=45.0,  # neutral-low; absence is common and weak evidence
            summary="No EXIF present (often stripped in transit).",
            metric=0.0,
            data={"has_timestamp": False, "has_gps": False},
        )

    names = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
    has_time = any(t in names for t in _TIME_TAGS)
    has_gps = _GPS_IFD in exif
    # Presence is a mild positive; still soft, never a gate.
    score = 60.0 + (15.0 if has_time else 0.0) + (10.0 if has_gps else 0.0)
    return CheckOutcome(
        NAME,
        available=True,
        score=min(100.0, score),
        summary="EXIF present" + (" with timestamp" if has_time else "") + ".",
        metric=float(len(exif)),
        data={"has_timestamp": has_time, "has_gps": has_gps},
    )
