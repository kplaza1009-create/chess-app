"""Private, unrated PGN archives; preserve all existing games and ratings."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imported_games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("headers", postgresql.JSONB(), nullable=False),
        sa.Column("initial_fen", sa.String(160), nullable=False),
        sa.Column("moves", postgresql.JSONB(), nullable=False),
        sa.Column("result", sa.String(7), nullable=False),
        sa.Column("ply_count", sa.Integer(), nullable=False),
        sa.Column("pgn", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("result IN ('*', '1-0', '0-1', '1/2-1/2')", name="result"),
        sa.CheckConstraint("ply_count BETWEEN 0 AND 1000", name="plies"),
        sa.CheckConstraint("octet_length(pgn) <= 131072", name="pgn_size"),
    )
    op.create_index(
        "ix_imported_games_owner_history",
        "imported_games",
        ["owner_id", sa.text("created_at DESC"), "id"],
    )


def downgrade() -> None:
    op.drop_table("imported_games")
