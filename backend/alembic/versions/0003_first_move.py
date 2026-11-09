"""First-move deadlines and unrated aborts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("first_move_deadline", sa.DateTime(timezone=True)))
    op.execute("UPDATE games SET rated=false WHERE status='aborted'")
    op.create_check_constraint(
        op.f("ck_games_aborted_unrated"), "games", "status <> 'aborted' OR NOT rated"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_games_aborted_unrated"), "games", type_="check")
    op.drop_column("games", "first_move_deadline")
