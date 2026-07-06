"""Recapture check — "photo of another screen" detection.

Three cheap, independent screen signatures, combined CONSERVATIVELY so real
scenes don't false-positive:
  * bezel   — a dark rectangular border framing a brighter interior (the screen)
  * moire   — a strong periodic peak in the FFT (pixel grid / screen-door)
  * glare   — a bright specular blob (monitor/phone reflection)

The combination is bezel-anchored: a photographed screen almost always shows a
dark frame around a brighter panel, whereas moire and glare each occur alone in
plenty of legitimate captures (fabric texture, sunlight). So we require the
bezel AND at least one corroborating signal. This deliberately under-flags
rather than over-flags (fail-open) — the vision check's
``looks_like_photo_of_a_screen`` is a second, independent line of defense.

This is the primary deterministic defense against laundered saved/AI images
photographed off a second screen under the live-camera lock. Detection constants
are detector internals (not per-tenant scoring policy); they are named here.
"""

from __future__ import annotations

from ..types import CheckOutcome
from ._imaging import CV2_AVAILABLE, load_gray

NAME = "recapture"

# --- detector thresholds (tuned so real captures stay well clear) ---
_MOIRE_PEAK_GATE = 200.0      # max/mean FFT energy in the high-freq band
_GLARE_FRACTION_GATE = 0.012  # fraction of near-white specular pixels
_BEZEL_CONTRAST_GATE = 55.0   # interior mean minus border mean (0-255)


def _moire_ratio(gray) -> float:
    import numpy as np

    g = gray.astype("float32")
    g -= g.mean()
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    h, w = spectrum.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    # High-frequency band only: exclude the low-freq disk (natural image energy).
    band = spectrum[radius > 0.18 * min(h, w)]
    if band.size == 0:
        return 0.0
    mean = float(band.mean()) + 1e-6
    return float(band.max() / mean)


def _glare_fraction(gray) -> float:

    return float((gray > 248).mean())


def _bezel_contrast(gray) -> float:
    import numpy as np

    h, w = gray.shape
    bw = max(1, int(0.08 * min(h, w)))  # border band width
    border = np.concatenate(
        [
            gray[:bw, :].ravel(),
            gray[-bw:, :].ravel(),
            gray[:, :bw].ravel(),
            gray[:, -bw:].ravel(),
        ]
    )
    interior = gray[bw:-bw, bw:-bw]
    if interior.size == 0:
        return 0.0
    return float(interior.mean() - border.mean())


def run(image_bytes: bytes) -> CheckOutcome:
    if not CV2_AVAILABLE:  # pragma: no cover
        return CheckOutcome(NAME, available=False, score=None, summary="OpenCV not installed.")

    gray = load_gray(image_bytes)
    if gray is None:
        return CheckOutcome(NAME, available=True, score=50.0, summary="Could not decode image.")

    moire = _moire_ratio(gray)
    glare = _glare_fraction(gray)
    bezel = _bezel_contrast(gray)

    moire_hit = moire >= _MOIRE_PEAK_GATE
    glare_hit = glare >= _GLARE_FRACTION_GATE
    bezel_hit = bezel >= _BEZEL_CONTRAST_GATE

    # Bezel-anchored: require the screen frame AND a corroborating signal.
    screen_detected = bezel_hit and (moire_hit or glare_hit)

    data = {
        "screen_detected": screen_detected,
        "moire_ratio": round(moire, 2),
        "glare_fraction": round(glare, 4),
        "bezel_contrast": round(bezel, 1),
        "signals": {"moire": moire_hit, "glare": glare_hit, "bezel": bezel_hit},
    }
    if screen_detected:
        return CheckOutcome(
            NAME, available=True, score=0.0,
            summary="Looks photographed off another screen (edge/glare/moire).",
            metric=round(moire, 2), data=data,
        )
    return CheckOutcome(
        NAME, available=True, score=100.0,
        summary="No screen-recapture signature detected.",
        metric=round(moire, 2), data=data,
    )
