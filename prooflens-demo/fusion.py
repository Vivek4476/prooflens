"""Fuse per-check results into a final 0-100 score + band.

Two-stage logic:
  1. Weighted blend of the soft signals (weights from config; unavailable
     checks are dropped and the remaining weights renormalised).
  2. Hard gates that can override the blend downward, regardless of the blend:
       - exact/near duplicate
       - looks like a photo of a screen
       - designed graphic / meme / screenshot
       - meeting_plausibility < gate
       - fully blurred
     Each fired gate caps the final score; the lowest cap wins.

Bands: Suspect < 40, Doubtful 40-70, Clear >= 70 (thresholds in config).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from config import THRESHOLDS, WEIGHTS
from checks.types import CheckResult


@dataclass
class Fused:
    score: float
    band: str
    gates_fired: List[str]


_WEIGHT_BY_NAME = {
    "content_relevance": WEIGHTS.content,
    "sharpness": WEIGHTS.sharpness,
    "person_presence": WEIGHTS.person,
    "uniqueness": WEIGHTS.uniqueness,
    "metadata": WEIGHTS.metadata,
}


def band_for(score: float) -> str:
    if score >= THRESHOLDS.band_clear:
        return "Clear"
    if score >= THRESHOLDS.band_doubtful:
        return "Doubtful"
    return "Suspect"


def _weighted_blend(checks: List[CheckResult]) -> float:
    total_w = 0.0
    acc = 0.0
    for c in checks:
        if not c.available:
            continue  # drop unavailable checks, renormalise over the rest
        w = _WEIGHT_BY_NAME.get(c.name, 0.0)
        if w <= 0:
            continue
        acc += w * c.score
        total_w += w
    if total_w == 0:
        return 50.0
    return acc / total_w


def fuse(checks: List[CheckResult], verdict: Dict[str, Any]) -> Fused:
    blend = _weighted_blend(checks)

    by_name = {c.name: c for c in checks}
    gates: List[tuple[str, float]] = []  # (label, cap)

    # --- Hard gates ---
    uniq = by_name.get("uniqueness")
    if uniq and uniq.available and uniq.metric is not None:
        if uniq.metric <= THRESHOLDS.dup_distance:
            gates.append(("exact_duplicate", 15.0))

    if verdict.get("looks_like_photo_of_a_screen"):
        gates.append(("photo_of_screen", 20.0))
    if verdict.get("is_designed_graphic"):
        gates.append(("designed_graphic", 20.0))
    if verdict.get("is_meme_or_screenshot"):
        gates.append(("meme_or_screenshot", 20.0))

    plaus = int(verdict.get("meeting_plausibility", 100))
    if plaus < THRESHOLDS.meeting_plausibility_gate:
        gates.append(("low_meeting_plausibility", 25.0))

    sharp = by_name.get("sharpness")
    if sharp and sharp.available and sharp.metric is not None:
        if sharp.metric <= THRESHOLDS.blur_floor:
            gates.append(("fully_blurred", 20.0))

    score = blend
    for _, cap in gates:
        score = min(score, cap)

    score = max(0.0, min(100.0, score))
    return Fused(
        score=round(score, 1),
        band=band_for(score),
        gates_fired=[label for label, _ in gates],
    )
