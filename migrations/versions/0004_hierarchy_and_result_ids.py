"""hierarchy table + promote rep_id/opportunity_id to Result columns (+ backfill)

Revision ID: 0004_hierarchy_and_result_ids
Revises: 0003_default_vision_groq
Create Date: 2026-07-08

Additive: adds two nullable columns to results (backfilled from jobs.payload),
a (tenant_id, rep_id) index, and the effective-dated hierarchy table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_hierarchy_and_result_ids"
down_revision = "0003_default_vision_groq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Promote rep_id / opportunity_id to real Result columns.
    op.add_column("results", sa.Column("rep_id", sa.String(200), nullable=True))
    op.add_column("results", sa.Column("opportunity_id", sa.String(200), nullable=True))
    op.create_index("ix_results_tenant_rep", "results", ["tenant_id", "rep_id"])

    # 2) Backfill from the originating job payload (normalized: trim + upper for rep_id).
    op.execute(
        """
        UPDATE results r
        SET rep_id = UPPER(TRIM(j.payload->>'rep_id')),
            opportunity_id = j.payload->>'opportunity_id'
        FROM jobs j
        WHERE r.job_id = j.id
          AND r.rep_id IS NULL
          AND NULLIF(TRIM(j.payload->>'rep_id'), '') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE results r
        SET opportunity_id = j.payload->>'opportunity_id'
        FROM jobs j
        WHERE r.job_id = j.id
          AND r.opportunity_id IS NULL
          AND NULLIF(TRIM(j.payload->>'opportunity_id'), '') IS NOT NULL
        """
    )

    # 3) Effective-dated hierarchy reference table.
    op.create_table(
        "hierarchy",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"), nullable=False,
        ),
        sa.Column("agent_id", sa.String(200), nullable=False),
        sa.Column("sm", sa.String(200), nullable=True),
        sa.Column("rsm", sa.String(200), nullable=True),
        sa.Column("srsm", sa.String(200), nullable=True),
        sa.Column("zonal_head", sa.String(200), nullable=True),
        sa.Column("branch", sa.String(200), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("upload_id", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_hierarchy_lookup", "hierarchy", ["tenant_id", "agent_id", "valid_from"]
    )


def downgrade() -> None:
    op.drop_index("ix_hierarchy_lookup", table_name="hierarchy")
    op.drop_table("hierarchy")
    op.drop_index("ix_results_tenant_rep", table_name="results")
    op.drop_column("results", "opportunity_id")
    op.drop_column("results", "rep_id")
