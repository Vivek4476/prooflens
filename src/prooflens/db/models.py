"""ORM models — Postgres does triple duty: tenants, queue, hash store, results,
audit, DLQ. Every table carries tenant_id and every query is tenant-scoped.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class JobStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"          # transient failure, will retry
    DEAD_LETTER = "dead_letter"  # exhausted attempts (DLQ)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Webhook HMAC secret (per tenant).
    webhook_secret: Mapped[str] = mapped_column(String(200))
    # LSQ API credentials, Fernet-encrypted at rest (key from env). NEVER logged.
    lsq_credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # LSQ custom-field ids for write-back {"band": "...", "score": "...", "reason": "..."}.
    field_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Per-tenant scoring overrides merged over ScoringConfig defaults.
    scoring_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    vision_backend: Mapped[str] = mapped_column(String(32), default="groq")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list[Job]] = relationship(back_populates="tenant")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Idempotency: one job per (tenant, external event id).
        UniqueConstraint("tenant_id", "event_id", name="uq_jobs_tenant_event"),
        # The queue drain scans by status + schedule.
        Index("ix_jobs_claimable", "status", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(200))

    status: Mapped[JobStatus] = mapped_column(
        # Persist the enum VALUES ("queued", ...) not the member names ("QUEUED"),
        # matching the Postgres enum created by the migration.
        Enum(JobStatus, name="job_status", values_callable=lambda e: [m.value for m in e]),
        default=JobStatus.QUEUED,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="jobs")


class ImageHash(Base):
    """The uniqueness store. Holds the dHash + trail ONLY — never images."""

    __tablename__ = "image_hashes"
    __table_args__ = (Index("ix_hashes_tenant", "tenant_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    dhash: Mapped[str] = mapped_column(String(16))  # 64-bit dHash as 16 hex chars
    rep_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    captured_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        # Effective-dated hierarchy join + rep_id filtering are per (tenant, rep).
        Index("ix_results_tenant_rep", "tenant_id", "rep_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )
    rep_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    band: Mapped[str] = mapped_column(String(16))
    score: Mapped[float] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    reason_code: Mapped[str] = mapped_column(String(64))
    rubric_version: Mapped[str] = mapped_column(String(16))
    checks: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Provenance: "direct" (/v1/score) | "webhook" (LSQ job) | "seed" (demo data).
    # Stored (not derived) so the realistic-seed script can mark rows honestly.
    source: Mapped[str] = mapped_column(String(16), default="direct")

    review_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Hierarchy(Base):
    """Effective-dated org map: one row per (agent, version). A result maps to
    the row with agent_id == result.rep_id and the LATEST valid_from <= scored
    date. Tenant-scoped; org changes never rewrite historical reports."""

    __tablename__ = "hierarchy"
    __table_args__ = (
        Index("ix_hierarchy_lookup", "tenant_id", "agent_id", "valid_from"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    agent_id: Mapped[str] = mapped_column(String(200))
    sm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rsm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    srsm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    zonal_head: Mapped[str | None] = mapped_column(String(200), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    upload_id: Mapped[str] = mapped_column(String(64))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
