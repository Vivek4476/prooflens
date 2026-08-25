"""add copilot_summary to results

Revision ID: 0008_copilot_summary
Revises: 0007_api_keys
Create Date: 2026-08-25

Additive: nullable Text column on results. No backfill required — existing
rows will have NULL (copilot_summary is generated at score-time going forward).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_copilot_summary"
down_revision = "0007_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("copilot_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "copilot_summary")
