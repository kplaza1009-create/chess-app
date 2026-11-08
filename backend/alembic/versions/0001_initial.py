"""Create users, refresh sessions, ratings, games, moves, and rating changes.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=24), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=60), nullable=False),
        sa.Column("avatar_key", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("username ~ '^[a-z0-9_]{3,24}$'", name=op.f("ck_users_username_format")),
        sa.CheckConstraint(
            "email = lower(email) AND length(email) > 3", name=op.f("ck_users_email_normalized")
        ),
        sa.CheckConstraint("length(password_hash) = 60", name=op.f("ck_users_bcrypt_hash_length")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "multiplayer", "computer", name="kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "finished",
                "aborted",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("white_user_id", sa.Uuid(), nullable=True),
        sa.Column("black_user_id", sa.Uuid(), nullable=True),
        sa.Column("ai_level", sa.Integer(), nullable=True),
        sa.Column("rated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "speed",
            sa.Enum(
                "bullet", "blitz", "rapid", name="speed", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("initial_time_ms", sa.Integer(), nullable=False),
        sa.Column("increment_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("initial_fen", sa.String(length=160), nullable=False),
        sa.Column("current_fen", sa.String(length=160), nullable=False),
        sa.Column("ply_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("white_remaining_ms", sa.Integer(), nullable=False),
        sa.Column("black_remaining_ms", sa.Integer(), nullable=False),
        sa.Column("turn_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(length=7), server_default=sa.text("'*'"), nullable=False),
        sa.Column("termination", sa.String(length=32), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'multiplayer' AND white_user_id IS NOT NULL "
            "AND black_user_id IS NOT NULL AND white_user_id <> black_user_id "
            "AND ai_level IS NULL) OR "
            "(kind = 'computer' AND ((white_user_id IS NULL) <> (black_user_id IS NULL)) "
            "AND ai_level IS NOT NULL AND ai_level BETWEEN 1 AND 3 AND NOT rated)",
            name=op.f("ck_games_participants"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND result = '*' AND termination IS NULL AND ended_at IS NULL) "
            "OR (status = 'finished' AND result IN ('1-0', '0-1', '1/2-1/2') "
            "AND termination IS NOT NULL AND termination <> 'aborted' AND ended_at IS NOT NULL) "
            "OR (status = 'aborted' AND result = '*' AND termination = 'aborted' "
            "AND ended_at IS NOT NULL)",
            name=op.f("ck_games_result_state"),
        ),
        sa.CheckConstraint(
            "termination IS NULL OR "
            "(result IN ('1-0', '0-1') AND termination IN ('checkmate', 'resignation', 'timeout')) "
            "OR (result = '1/2-1/2' AND termination IN ('stalemate', 'repetition', 'fifty_move', "
            "'seventy_five_move', 'insufficient_material', 'agreement', 'timeout')) "
            "OR (result = '*' AND termination = 'aborted')",
            name=op.f("ck_games_termination_result"),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= created_at", name=op.f("ck_games_end_after_creation")
        ),
        sa.CheckConstraint(
            "initial_time_ms BETWEEN 1000 AND 10800000 AND increment_ms BETWEEN 0 AND 180000",
            name=op.f("ck_games_time_control"),
        ),
        sa.CheckConstraint(
            "ply_count >= 0 AND version >= 0", name=op.f("ck_games_counters_nonnegative")
        ),
        sa.CheckConstraint(
            "white_remaining_ms >= 0 AND black_remaining_ms >= 0",
            name=op.f("ck_games_clocks_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["black_user_id"],
            ["users.id"],
            name=op.f("fk_games_black_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["white_user_id"],
            ["users.id"],
            name=op.f("fk_games_white_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
    )
    op.create_index(
        "ix_games_black_history",
        "games",
        ["black_user_id", sa.literal_column("created_at DESC"), "id"],
        unique=False,
    )
    op.create_index("ix_games_status", "games", ["status"], unique=False)
    op.create_index(
        "ix_games_white_history",
        "games",
        ["white_user_id", sa.literal_column("created_at DESC"), "id"],
        unique=False,
    )
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_refresh_sessions_token_hash_format")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_refresh_sessions_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_sessions_token_hash")),
    )
    op.create_index(
        "ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_sessions_user_id"), "refresh_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "user_ratings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "speed",
            sa.Enum(
                "bullet", "blitz", "rapid", name="speed", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), server_default=sa.text("1200"), nullable=False),
        sa.Column("wins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("losses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("draws", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("rating >= 0", name=op.f("ck_user_ratings_rating_nonnegative")),
        sa.CheckConstraint(
            "wins >= 0 AND losses >= 0 AND draws >= 0",
            name=op.f("ck_user_ratings_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_ratings_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", "speed", name=op.f("pk_user_ratings")),
    )
    op.create_index(
        "ix_user_ratings_leaderboard",
        "user_ratings",
        ["speed", sa.literal_column("rating DESC"), "user_id"],
        unique=False,
    )
    op.create_table(
        "moves",
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("uci", sa.String(length=5), nullable=False),
        sa.Column("san", sa.String(length=16), nullable=False),
        sa.Column("fen_after", sa.String(length=160), nullable=False),
        sa.Column("white_remaining_ms", sa.Integer(), nullable=False),
        sa.Column("black_remaining_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "uci ~ '^[a-h][1-8][a-h][1-8][qrbn]?$'", name=op.f("ck_moves_uci_format")
        ),
        sa.CheckConstraint("length(san) > 0", name=op.f("ck_moves_san_nonempty")),
        sa.CheckConstraint("ply >= 1", name=op.f("ck_moves_ply_positive")),
        sa.CheckConstraint(
            "white_remaining_ms >= 0 AND black_remaining_ms >= 0",
            name=op.f("ck_moves_clocks_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"], ["games.id"], name=op.f("fk_moves_game_id_games"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("game_id", "ply", name=op.f("pk_moves")),
        sa.UniqueConstraint("game_id", "client_request_id", name="uq_moves_game_request"),
    )
    op.create_table(
        "rating_changes",
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "speed",
            sa.Enum(
                "bullet", "blitz", "rapid", name="speed", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("rating_before", sa.Integer(), nullable=False),
        sa.Column("rating_after", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating_before >= 0 AND rating_after >= 0",
            name=op.f("ck_rating_changes_ratings_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_rating_changes_game_id_games"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "speed"],
            ["user_ratings.user_id", "user_ratings.speed"],
            name=op.f("fk_rating_changes_user_id_user_ratings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("game_id", "user_id", name=op.f("pk_rating_changes")),
    )
    op.create_index("ix_rating_changes_user_id", "rating_changes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("rating_changes")
    op.drop_table("moves")
    op.drop_table("user_ratings")
    op.drop_table("refresh_sessions")
    op.drop_table("games")
    op.drop_table("users")
