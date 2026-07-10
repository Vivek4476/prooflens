"""results.source: STORED provenance column ("direct" | "webhook" | "seed")

Revision ID: 0005_result_source
Revises: 0004_hierarchy_and_result_ids
Create Date: 2026-07-09

Additive: adds a NOT NULL results.source column (server_default "direct"), then
backfills existing webhook-originated rows honestly so history isn't relabeled.
Today's behavior derives source from job_id ("webhook" if job_id else "direct");
this migration promotes that same derivation into a stored value. No existing
row's *observed* source changes — only seeded rows will ever show "seed".
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_result_source"
down_revision = "0004_hierarchy_and_result_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "results",
        sa.Column("source", sa.String(16), nullable=False, server_default="direct"),
    )
    # The server_default already covers direct/null-job_id rows; only webhook
    # rows (job_id IS NOT NULL) need backfilling away from the default.
    op.execute("UPDATE results SET source = 'webhook' WHERE job_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("results", "source")
