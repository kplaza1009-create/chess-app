"""Add shared authentication rate limits.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_throttles",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts > 0", name=op.f("ck_auth_throttles_attempts_positive")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_auth_throttles")),
    )
    op.create_index(op.f("ix_auth_throttles_expires_at"), "auth_throttles", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_throttles")
