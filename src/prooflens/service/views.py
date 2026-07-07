"""Plain value views passed across the application seam (no ORM, no DB types)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..engine.scoring_config import ScoringConfig


@dataclass(frozen=True)
class TenantView:
    id: str
    slug: str
    webhook_secret: str
    field_map: dict[str, str]        # {"band": "...", "score": "...", "reason": "..."}
    scoring: ScoringConfig
    vision_backend: str = "stub"


@dataclass
class JobView:
    id: str
    tenant_id: str
    event_id: str
    payload: dict = field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 5


@dataclass
class ResultView:
    """A stored scoring result, read back for History/Analytics (read-only)."""

    id: str
    created_at: str          # ISO 8601
    tenant_id: str
    band: str
    score: float
    reason: str
    reason_code: str
    rubric_version: str
    checks: list = field(default_factory=list)
    processing_ms: float = 0.0
    source: str = "direct"   # "webhook" (came via LSQ) | "direct" (scored via /v1/score)
    opportunity_id: str | None = None
    rep_id: str | None = None
    review_status: str | None = None   # approve|reject|false_positive|escalate; None = pending
    review_note: str | None = None
    reviewed_at: str | None = None     # ISO 8601
    reviewer: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "band": self.band,
            "score": self.score,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "rubric_version": self.rubric_version,
            "processing_ms": round(self.processing_ms, 1),
            "source": self.source,
            "opportunity_id": self.opportunity_id,
            "rep_id": self.rep_id,
            "checks": self.checks,
            "review": self._review_dict(),
        }

    def _review_dict(self) -> dict | None:
        if self.review_status is None:
            return None
        return {
            "status": self.review_status,
            "note": self.review_note,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer,
        }
