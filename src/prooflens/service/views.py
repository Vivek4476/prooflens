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
