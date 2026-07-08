"""Default new tenants' vision_backend to groq (stub is now test-only).

Existing rows are left as-is; operators change per-tenant backends explicitly.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_default_vision_groq"
down_revision = "0002_review_and_absli_rename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tenants", "vision_backend",
        existing_type=sa.String(32), existing_nullable=False,
        server_default="groq",
    )


def downgrade() -> None:
    op.alter_column(
        "tenants", "vision_backend",
        existing_type=sa.String(32), existing_nullable=False,
        server_default="stub",
    )
