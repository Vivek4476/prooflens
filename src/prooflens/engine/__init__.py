"""ProofLens scoring engine — a PURE LIBRARY.

Imports NO http/queue/lsq code. ``score(image_bytes, context) -> Verdict``.
The vision backend and hash store are injected via :class:`EngineContext`.
"""

from __future__ import annotations

from .hashstore import InMemoryHashStore
from .pipeline import score
from .scoring_config import (
    DEFAULT_SCORING,
    Bands,
    Caps,
    ScoringConfig,
    Thresholds,
    Weights,
)
from .types import CheckOutcome, EngineContext, HashMatch, HashStore, Verdict
from .verdicts import BANDS, REASON_TEXT, Reason

__all__ = [
    "score",
    "Verdict",
    "CheckOutcome",
    "EngineContext",
    "HashStore",
    "HashMatch",
    "InMemoryHashStore",
    "ScoringConfig",
    "DEFAULT_SCORING",
    "Weights",
    "Thresholds",
    "Caps",
    "Bands",
    "Reason",
    "REASON_TEXT",
    "BANDS",
]
