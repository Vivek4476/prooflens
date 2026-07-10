"""hierarchy.agent_name: optional DSE display name (from the hierarchy CSV)

Revision ID: 0006_agent_name
Revises: 0005_result_source
Create Date: 2026-07-10

Additive: adds a nullable results-adjacent column — hierarchy.agent_name —
so DSEs have a human-readable name instead of only agent_id. Nullable/optional
so existing hierarchy CSVs (without a name column) keep uploading unchanged;
absent -> the display falls back to agent_id (see service/hierarchy.py's
agent_display_name).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_agent_name"
down_revision = "0005_result_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hierarchy", sa.Column("agent_name", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("hierarchy", "agent_name")
