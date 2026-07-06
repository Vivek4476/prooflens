"""initial schema: tenants, jobs (queue/DLQ), image_hashes, results, audit_log

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def _fk_uuid(name: str, target: str, *, nullable: bool):
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target), nullable=nullable
    )


JOB_STATUS = postgresql.ENUM(
    "queued", "in_progress", "done", "failed", "dead_letter",
    name="job_status",
    create_type=False,  # created explicitly below, so create_table won't duplicate it
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("webhook_secret", sa.String(200), nullable=False),
        sa.Column("lsq_credentials_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("field_map", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("scoring_overrides", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("vision_backend", sa.String(32), nullable=False, server_default="stub"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    JOB_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _fk_uuid("tenant_id", "tenants.id", nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False, server_default="queued"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_jobs_tenant_event"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_claimable", "jobs", ["status", "scheduled_at"])

    op.create_table(
        "image_hashes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _fk_uuid("tenant_id", "tenants.id", nullable=False),
        sa.Column("dhash", sa.String(16), nullable=False),
        sa.Column("rep_id", sa.String(200), nullable=True),
        sa.Column("opportunity_id", sa.String(200), nullable=True),
        sa.Column("captured_at", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_hashes_tenant", "image_hashes", ["tenant_id"])

    op.create_table(
        "results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _fk_uuid("tenant_id", "tenants.id", nullable=False),
        _fk_uuid("job_id", "jobs.id", nullable=True),
        sa.Column("band", sa.String(16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("rubric_version", sa.String(16), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("results")
    op.drop_index("ix_hashes_tenant", table_name="image_hashes")
    op.drop_table("image_hashes")
    op.drop_index("ix_jobs_claimable", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_tenant_id", table_name="jobs")
    op.drop_table("jobs")
    JOB_STATUS.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
