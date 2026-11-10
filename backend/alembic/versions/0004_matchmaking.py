"""Persistent matchmaking leases and active rated game lookups."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matchmaking_tickets",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("time_control", sa.String(5), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["refresh_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ticket_id"),
        sa.CheckConstraint("expires_at > joined_at", name="lease_after_join"),
        sa.CheckConstraint(
            "time_control IN ('1+0', '3+2', '5+0', '10+0', '15+10')", name="time_control"
        ),
    )
    op.create_index(
        "ix_matchmaking_tickets_pool",
        "matchmaking_tickets",
        ["time_control", "joined_at", "user_id"],
    )
    op.create_index("ix_matchmaking_tickets_expires_at", "matchmaking_tickets", ["expires_at"])
    for color in ("white", "black"):
        op.create_index(
            f"ix_games_active_rated_{color}",
            "games",
            [f"{color}_user_id"],
            postgresql_where=sa.text("rated AND status = 'active'"),
        )


def downgrade() -> None:
    for color in ("white", "black"):
        op.drop_index(f"ix_games_active_rated_{color}", table_name="games")
    op.drop_table("matchmaking_tickets")
