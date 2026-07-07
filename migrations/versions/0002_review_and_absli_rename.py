"""results review columns + rename seeded demo tenant to ABSLI

Revision ID: 0002_review_and_absli_rename
Revises: 0001_initial
Create Date: 2026-07-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_review_and_absli_rename"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("review_status", sa.String(24), nullable=True))
    op.add_column("results", sa.Column("review_note", sa.String(500), nullable=True))
    op.add_column("results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("results", sa.Column("reviewer", sa.String(120), nullable=True))
    # Rename the seeded demo tenant to the real ABSLI identity (idempotent).
    op.execute(
        "UPDATE tenants SET name = 'Aditya Birla Sun Life Insurance' "
        "WHERE slug = 'dev' AND name = 'Dev Tenant'"
    )


def downgrade() -> None:
    op.drop_column("results", "reviewer")
    op.drop_column("results", "reviewed_at")
    op.drop_column("results", "review_note")
    op.drop_column("results", "review_status")
    op.execute(
        "UPDATE tenants SET name = 'Dev Tenant' "
        "WHERE slug = 'dev' AND name = 'Aditya Birla Sun Life Insurance'"
    )
