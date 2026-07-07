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
        pc = int(d.get("people_count", 0))
        if pc == 0:
            fired.append((Reason.NO_PEOPLE_OR_IRRELEVANT, caps.no_people))
        elif int(d.get("plausibility", 100)) < cfg.thresholds.plausibility_gate:
            fired.append((Reason.NO_PEOPLE_OR_IRRELEVANT, caps.low_plausibility))

        # A valid proof-of-meeting needs >=2 people in a genuine interaction. These
        # meeting gates fire ONLY on a real capture (red flags handled above) and
        # ONLY when the model is confident — an ambiguous read lowers confidence,
        # it does not manufacture a flag. Both cap to Doubtful, never Suspect.
        not_flag = not (
            d.get("looks_like_photo_of_a_screen")
            or d.get("is_designed_graphic")
            or d.get("is_meme_or_screenshot")
        )
        conf_high = str(d.get("context_confidence", "")).lower() == "high"
        vc = d.get("visit_context")
        clearly_no_visit = vc is not None and int(vc) < cfg.thresholds.no_visit_suspect_gate
        if pc > 0 and not_flag:
            if conf_high:
                # STRONG relevance gate: confident AND the visit context is near-absent
                # — the scene is clearly not a customer visit at all (a pool, gym,
                # tourist selfie). This is the ONE meeting gate that caps to Suspect;
                # stricter than the Doubtful gates below so genuine but unusual field
                # visits (rural home, roadside) are not hard-flagged.
                if clearly_no_visit:
                    fired.append((Reason.NOT_A_VISIT, caps.not_a_visit))
                # Milder meeting gates — a real capture that just lacks meeting
                # evidence. These cap to Doubtful, never Suspect.
                if pc == 1:
                    # A lone individual is never evidence of a meeting.
                    fired.append((Reason.SINGLE_PERSON, caps.weak_visit_context))
                elif vc is not None and int(vc) < cfg.thresholds.visit_context_gate:
                    # >=2 people but no genuine interaction (posed group, no exchange).
                    fired.append((Reason.NO_VISIT_CONTEXT, caps.weak_visit_context))
            elif clearly_no_visit:
                # Not highly confident, but the scene still reads as clearly NOT a visit
                # (visit_context near zero). Worth a human glance -> Doubtful, never
                # Suspect: an unsure read must not manufacture a hard flag.
                fired.append((Reason.NO_VISIT_CONTEXT, caps.weak_visit_context))
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
