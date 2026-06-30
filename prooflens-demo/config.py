"""
Central configuration for the ProofLens demo.

Everything tunable — check weights, gate thresholds, band cut-offs, model
names — lives here so you can tweak behaviour without touching logic. Values
can be overridden with environment variables (see `.env.example`); the defaults
below are chosen so the app runs sensibly out of the box.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ----------------------------------------------------------------------------
# Vision backend selection
# ----------------------------------------------------------------------------
# Which pluggable vision backend to use. Default "stub" => zero network, zero
# keys, app runs out of the box. Other options: anthropic | gemini | openai | local
VISION_BACKEND = os.getenv("VISION_BACKEND", "stub").strip().lower()

# Per-backend model ids (overridable via env).
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Local (OpenAI-compatible) endpoint, e.g. Ollama or vLLM serving Qwen2-VL / Moondream.
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen2-vl:2b")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "ollama")  # most local servers ignore this

# Long edge (px) we resize to before sending to the model — cuts tokens/latency.
VISION_MAX_EDGE = _env_int("VISION_MAX_EDGE", 768)


# ----------------------------------------------------------------------------
# Approx cost per photo (USD) for the bake-off table. Rough public list prices;
# adjust as pricing changes. Stub/local are free.
# ----------------------------------------------------------------------------
COST_PER_PHOTO_USD = {
    "anthropic": _env_float("COST_ANTHROPIC", 0.0020),
    "gemini": _env_float("COST_GEMINI", 0.0004),
    "openai": _env_float("COST_OPENAI", 0.0015),
    "local": 0.0,
    "stub": 0.0,
}


@dataclass(frozen=True)
class Weights:
    """Relative weight of each soft signal in the fused 0-100 score.

    These apply to the *soft* blend only. Hard gates (see below) can override
    the blend entirely. Weights are normalised at fuse time, so absolute scale
    does not matter — only the ratios do.
    """

    content: float = 0.45   # the star: is this the right scene?
    sharpness: float = 0.15
    person: float = 0.20
    uniqueness: float = 0.15
    metadata: float = 0.05


@dataclass(frozen=True)
class Thresholds:
    # --- sharpness (OpenCV Laplacian variance) ---
    # Below `blur_floor` => treated as fully blurred (hard gate). Between floor
    # and `sharp_ok` the score ramps linearly.
    blur_floor: float = field(default_factory=lambda: _env_float("SHARP_BLUR_FLOOR", 40.0))
    sharp_ok: float = field(default_factory=lambda: _env_float("SHARP_OK", 150.0))

    # --- uniqueness (dHash Hamming distance vs the local store) ---
    # <= dup_distance => exact/near duplicate (hard gate).
    dup_distance: int = field(default_factory=lambda: _env_int("DUP_DISTANCE", 5))
    # >= unique_distance => comfortably unique (full marks).
    unique_distance: int = field(default_factory=lambda: _env_int("UNIQUE_DISTANCE", 12))

    # --- content / relevance (vision model) ---
    meeting_plausibility_gate: int = field(
        default_factory=lambda: _env_int("MEETING_PLAUSIBILITY_GATE", 30)
    )

    # --- bands ---
    band_clear: float = field(default_factory=lambda: _env_float("BAND_CLEAR", 70.0))
    band_doubtful: float = field(default_factory=lambda: _env_float("BAND_DOUBTFUL", 40.0))


WEIGHTS = Weights()
THRESHOLDS = Thresholds()

# SQLite file for the uniqueness store (hashes + fake trail only — never images).
DB_PATH = os.getenv("PROOFLENS_DB", os.path.join(os.path.dirname(__file__), "prooflens.db"))
