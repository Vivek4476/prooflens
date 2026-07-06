"""Core engine value types: Verdict, CheckOutcome, EngineContext, HashStore.

Pure library types. The engine imports NO http/queue/lsq code; the vision
backend and hash store are injected via :class:`EngineContext`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..vision.base import VisionBackend
from .scoring_config import ScoringConfig
from .verdicts import Reason


@dataclass
class CheckOutcome:
    """One check's contribution to the fused score — the per-check breakdown."""

    name: str
    available: bool           # False => optional dep missing / not run; neutral
    score: float | None    # 0-100 contribution, or None when not applicable
    summary: str              # short internal description (NOT shown to reps)
    metric: float | None = None      # raw underlying number, if any
    data: dict[str, Any] = field(default_factory=dict)  # extra structured detail
    latency_ms: float | None = None  # wall-clock time this check took (set by the pipeline)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    """The engine's output. Ordered verdict-first, evidence-second, internals-last."""

    score: float
    band: str
    reason: str               # human-readable, from the fixed vocabulary
    reason_code: str          # the Reason enum value behind `reason`
    checks: list[CheckOutcome]
    rubric_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            # verdict first
            "band": self.band,
            "score": self.score,
            "reason": self.reason,
            "reason_code": self.reason_code,
            # evidence second
            "checks": [c.to_dict() for c in self.checks],
            # internals last
            "rubric_version": self.rubric_version,
        }


@dataclass
class HashMatch:
    """Closest prior hash for a tenant, with its (non-image) provenance trail."""

    distance: int
    dhash: str
    rep_id: str | None = None
    opportunity_id: str | None = None
    created_at: str | None = None


@runtime_checkable
class HashStore(Protocol):
    """Tenant-scoped perceptual-hash store. Stores hashes + trail, NEVER images."""

    def nearest(self, tenant_id: str, dhash_hex: str) -> HashMatch | None:
        ...

    def remember(
        self,
        tenant_id: str,
        dhash_hex: str,
        *,
        rep_id: str | None = None,
        opportunity_id: str | None = None,
        captured_at: str | None = None,
    ) -> None:
        ...


@dataclass
class EngineContext:
    """Everything the pure engine needs to score one image, resolved per tenant."""

    tenant_id: str
    vision: VisionBackend
    hash_store: HashStore
    scoring: ScoringConfig
    rep_id: str | None = None
    opportunity_id: str | None = None
    captured_at: str | None = None
    remember_hash: bool = True  # store this image's hash after scoring


# Re-exported for convenience.
__all__ = [
    "CheckOutcome",
    "Verdict",
    "HashMatch",
    "HashStore",
    "EngineContext",
    "Reason",
]
