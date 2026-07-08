"""Webhook request/response schemas.

PLACEHOLDER PAYLOAD SHAPE (see README TODOs): the real LSQ webhook body is not
yet confirmed. This mirror is intentionally permissive and isolated so only this
model changes once the real shape is known. The live-camera lock means an image
should arrive; we accept it inline as base64 or by reference (URL, Phase 3).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..service.ids import normalize_id


class WebhookPayload(BaseModel):
    event_id: str = Field(..., description="Idempotency key — one job per (tenant, event).")
    opportunity_id: str = Field(..., description="LSQ opportunity/lead id to write back to.")
    rep_id: str | None = Field(default=None, description="Field rep id (uniqueness trail).")
    captured_at: str | None = Field(default=None, description="Capture timestamp, if provided.")

    # Image: inline bytes now; by-reference fetch is a Phase 3 TODO.
    image_base64: str | None = Field(default=None)
    image_url: str | None = Field(default=None)

    @field_validator("rep_id")
    @classmethod
    def _normalize_rep_id(cls, v: str | None) -> str | None:
        # Normalize at ingestion so every stored rep_id is already canonical
        # (matches the hierarchy upload's normalization — one shared rule).
        return normalize_id(v)


class WebhookAck(BaseModel):
    status: str          # "accepted" | "duplicate"
    job_id: str
