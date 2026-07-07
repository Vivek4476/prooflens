"""Scoring configuration — weights, thresholds and gate caps.

Pure: imports nothing but pydantic. These are the *defaults*; every value is
resolved per-tenant by the service (tenants may override any field), so there
are no magic numbers buried in the fusion logic — they all live here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Weights(BaseModel):
    """Relative weight of each soft signal in the fused 0-100 blend.

    Applies to the soft blend only; hard gates (see :class:`Caps`) can override
    the blend downward. Weights are renormalised over the *available* checks at
    fuse time, so only the ratios matter.
    """

    content: float = 0.50  # the star: real captured scene vs screen/graphic/object
    sharpness: float = 0.15
    uniqueness: float = 0.25
    metadata: float = 0.10


class Thresholds(BaseModel):
    # --- sharpness (OpenCV Laplacian variance) ---
    blur_floor: float = 40.0   # <= this => unreadable (quality gate: "retake")
    sharp_ok: float = 150.0    # >= this => full marks; linear ramp in between

    # --- uniqueness (dHash Hamming distance vs tenant-scoped hash store) ---
    dup_exact: int = 0         # <= this => exact duplicate (hard gate)
    dup_near: int = 6          # <= this => near-duplicate (flag)
    unique_distance: int = 12  # >= this => comfortably unique (full marks)

    # --- content / relevance (vision model) ---
    plausibility_gate: int = 30  # < this => scene reads as irrelevant (not a real capture)
    visit_context_gate: int = 35  # < this (with high confidence) => no apparent visit


class Caps(BaseModel):
    """Score ceilings applied when a gate fires. The lowest fired cap wins.

    Chosen so integrity failures land in Suspect (<40) and quality issues land
    no worse than Doubtful — sharpness alone is never a heavy penalty.
    """

    duplicate: float = 15.0          # exact duplicate  -> Suspect
    near_duplicate: float = 55.0     # near duplicate   -> Doubtful
    screen_recapture: float = 20.0   # photo of a screen-> Suspect
    designed_graphic: float = 20.0   # graphic/meme/shot-> Suspect
    no_people: float = 30.0          # empty/irrelevant -> Suspect
    low_plausibility: float = 45.0   # people but odd   -> Doubtful
    weak_visit_context: float = 55.0 # real, no visit   -> Doubtful (never Suspect)
    too_blurred: float = 55.0        # unreadable       -> Doubtful
    no_content: float = 69.0         # vision unavailable-> never Clear (Doubtful)


class Bands(BaseModel):
    clear: float = 70.0     # >= clear
    doubtful: float = 40.0  # >= doubtful, else suspect


class ScoringConfig(BaseModel):
    """Everything the engine needs to turn checks into a Verdict, per tenant."""

    weights: Weights = Field(default_factory=Weights)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    caps: Caps = Field(default_factory=Caps)
    bands: Bands = Field(default_factory=Bands)


DEFAULT_SCORING = ScoringConfig()
