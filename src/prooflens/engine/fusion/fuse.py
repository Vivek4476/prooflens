"""Fusion — blend the soft signals, apply hard-gate floors, pick the reason.

No single check decides. The soft blend is a weighted, renormalised average of
the available signals; independent hard gates can only cap the score DOWNWARD
(the lowest fired cap wins). The human-readable reason is chosen from the fixed
vocabulary by severity — see prooflens.engine.verdicts.

Every threshold/weight/cap is resolved per-tenant via ScoringConfig; there are
no magic numbers in this logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..scoring_config import ScoringConfig
from ..types import CheckOutcome
from ..verdicts import (
    BAND_CLEAR,
    BAND_DOUBTFUL,
    BAND_SUSPECT,
    Reason,
    most_severe,
    reason_text,
)

# Which checks feed the soft blend, and via which weight. `recapture` is a pure
# gate (not blended); `exif` maps to the `metadata` weight.
_BLEND_WEIGHT_ATTR = {
    "content": "content",
    "sharpness": "sharpness",
    "uniqueness": "uniqueness",
    "exif": "metadata",
}


@dataclass
class FusionResult:
    score: float
    band: str
    reason: str
    reason_code: str


def _blend(checks: dict[str, CheckOutcome], cfg: ScoringConfig) -> float:
    total_w = 0.0
    acc = 0.0
    for name, attr in _BLEND_WEIGHT_ATTR.items():
        c = checks.get(name)
        if c is None or not c.available or c.score is None:
            continue
        w = getattr(cfg.weights, attr)
        if w <= 0:
            continue
        acc += w * c.score
        total_w += w
    return acc / total_w if total_w else 50.0


def _band_for(score: float, cfg: ScoringConfig) -> str:
    if score >= cfg.bands.clear:
        return BAND_CLEAR
    if score >= cfg.bands.doubtful:
        return BAND_DOUBTFUL
    return BAND_SUSPECT


def _gates(checks: dict[str, CheckOutcome], cfg: ScoringConfig) -> list[tuple[Reason, float]]:
    """Return (reason, score_cap) for every hard gate that fired."""
    caps = cfg.caps
    fired: list[tuple[Reason, float]] = []

    uniq = checks.get("uniqueness")
    if uniq and uniq.available:
        if uniq.data.get("exact_duplicate"):
            fired.append((Reason.RECYCLED, caps.duplicate))
        elif uniq.data.get("near_duplicate"):
            fired.append((Reason.RECYCLED, caps.near_duplicate))

    recap = checks.get("recapture")
    if recap and recap.available and recap.data.get("screen_detected"):
        fired.append((Reason.SCREEN_RECAPTURE, caps.screen_recapture))

    content = checks.get("content")
    if content is not None and content.available:
        d = content.data
        if d.get("looks_like_photo_of_a_screen"):
            fired.append((Reason.SCREEN_RECAPTURE, caps.screen_recapture))
        if d.get("is_designed_graphic") or d.get("is_meme_or_screenshot"):
            fired.append((Reason.DESIGNED_GRAPHIC, caps.designed_graphic))
        if int(d.get("people_count", 0)) == 0:
            fired.append((Reason.NO_PEOPLE_OR_IRRELEVANT, caps.no_people))
        elif int(d.get("plausibility", 100)) < cfg.thresholds.plausibility_gate:
            fired.append((Reason.NO_PEOPLE_OR_IRRELEVANT, caps.low_plausibility))
    elif content is not None and not content.available:
        # Vision unavailable: score without it, but never award Clear.
        fired.append((Reason.NO_CONTENT_ANALYSIS, caps.no_content))

    blur = checks.get("sharpness")
    if blur and blur.available and blur.data.get("too_blurred"):
        fired.append((Reason.TOO_BLURRED, caps.too_blurred))

    return fired


def fuse(outcomes: list[CheckOutcome], cfg: ScoringConfig) -> FusionResult:
    checks = {c.name: c for c in outcomes}

    score = _blend(checks, cfg)
    fired = _gates(checks, cfg)
    for _, cap in fired:
        score = min(score, cap)
    score = max(0.0, min(100.0, round(score, 1)))

    reason_code = most_severe([r for r, _ in fired])
    return FusionResult(
        score=score,
        band=_band_for(score, cfg),
        reason=reason_text(reason_code),
        reason_code=reason_code.value,
    )
