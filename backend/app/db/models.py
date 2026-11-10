from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class Speed(StrEnum):
    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"


class TimeControl(StrEnum):
    BULLET_1 = "1+0"
    BLITZ_3_2 = "3+2"
    BLITZ_5 = "5+0"
    RAPID_10 = "10+0"
    RAPID_15_10 = "15+10"


class GameKind(StrEnum):
    MULTIPLAYER = "multiplayer"
    COMPUTER = "computer"


class GameStatus(StrEnum):
    ACTIVE = "active"
    FINISHED = "finished"
    ABORTED = "aborted"


def db_enum(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class User(CreatedAt, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username ~ '^[a-z0-9_]{3,24}$'", name="username_format"),
        CheckConstraint("email = lower(email) AND length(email) > 3", name="email_normalized"),
        CheckConstraint("length(password_hash) = 60", name="bcrypt_hash_length"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(60))
    avatar_key: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class RefreshSession(CreatedAt, Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_format"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_refresh_sessions_family_id", "family_id"),
        Index("ix_refresh_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[UUID] = mapped_column(default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserRating(Base):
    __tablename__ = "user_ratings"
    __table_args__ = (
        CheckConstraint("rating >= 0", name="rating_nonnegative"),
        CheckConstraint("wins >= 0 AND losses >= 0 AND draws >= 0", name="counts_nonnegative"),
        Index("ix_user_ratings_leaderboard", "speed", text("rating DESC"), "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    speed: Mapped[Speed] = mapped_column(db_enum(Speed, "speed"), primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, server_default=text("1200"))
    wins: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    losses: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    draws: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class Game(CreatedAt, Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'multiplayer' AND white_user_id IS NOT NULL "
            "AND black_user_id IS NOT NULL AND white_user_id <> black_user_id "
            "AND ai_level IS NULL) OR "
            "(kind = 'computer' AND ((white_user_id IS NULL) <> (black_user_id IS NULL)) "
            "AND ai_level IS NOT NULL AND ai_level BETWEEN 1 AND 3 AND NOT rated)",
            name="participants",
        ),
        CheckConstraint(
            "initial_time_ms BETWEEN 1000 AND 10800000 AND increment_ms BETWEEN 0 AND 180000",
            name="time_control",
        ),
        CheckConstraint(
            "white_remaining_ms >= 0 AND black_remaining_ms >= 0", name="clocks_nonnegative"
        ),
        CheckConstraint("ply_count >= 0 AND version >= 0", name="counters_nonnegative"),
        CheckConstraint("status <> 'aborted' OR NOT rated", name="aborted_unrated"),
        CheckConstraint(
            "(status = 'active' AND result = '*' AND termination IS NULL AND ended_at IS NULL) "
            "OR (status = 'finished' AND result IN ('1-0', '0-1', '1/2-1/2') "
            "AND termination IS NOT NULL AND termination <> 'aborted' AND ended_at IS NOT NULL) "
            "OR (status = 'aborted' AND result = '*' AND termination = 'aborted' "
            "AND ended_at IS NOT NULL)",
            name="result_state",
        ),
        CheckConstraint(
            "termination IS NULL OR "
            "(result IN ('1-0', '0-1') AND termination IN ('checkmate', 'resignation', 'timeout')) "
            "OR (result = '1/2-1/2' AND termination IN ('stalemate', 'repetition', 'fifty_move', "
            "'seventy_five_move', 'insufficient_material', 'agreement', 'timeout')) "
            "OR (result = '*' AND termination = 'aborted')",
            name="termination_result",
        ),
        CheckConstraint("ended_at IS NULL OR ended_at >= created_at", name="end_after_creation"),
        Index("ix_games_white_history", "white_user_id", text("created_at DESC"), "id"),
        Index("ix_games_black_history", "black_user_id", text("created_at DESC"), "id"),
        Index("ix_games_status", "status"),
        Index(
            "ix_games_active_rated_white",
            "white_user_id",
            postgresql_where=text("rated AND status = 'active'"),
        ),
        Index(
            "ix_games_active_rated_black",
            "black_user_id",
            postgresql_where=text("rated AND status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[GameKind] = mapped_column(db_enum(GameKind, "kind"))
    status: Mapped[GameStatus] = mapped_column(
        db_enum(GameStatus, "status"), server_default=text("'active'")
    )
    white_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    black_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ai_level: Mapped[int | None] = mapped_column(Integer)
    rated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    speed: Mapped[Speed] = mapped_column(db_enum(Speed, "speed"))
    initial_time_ms: Mapped[int] = mapped_column(Integer)
    increment_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    initial_fen: Mapped[str] = mapped_column(String(160), default=START_FEN)
    current_fen: Mapped[str] = mapped_column(String(160), default=START_FEN)
    ply_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    white_remaining_ms: Mapped[int] = mapped_column(Integer)
    black_remaining_ms: Mapped[int] = mapped_column(Integer)
    turn_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_move_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str] = mapped_column(String(7), server_default=text("'*'"))
    termination: Mapped[str | None] = mapped_column(String(32))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchmakingTicket(Base):
    __tablename__ = "matchmaking_tickets"
    __table_args__ = (
        CheckConstraint("expires_at > joined_at", name="lease_after_join"),
        Index("ix_matchmaking_tickets_pool", "time_control", "joined_at", "user_id"),
        Index("ix_matchmaking_tickets_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    session_id: Mapped[UUID] = mapped_column(ForeignKey("refresh_sessions.id", ondelete="CASCADE"))
    ticket_id: Mapped[UUID] = mapped_column(default=uuid4, unique=True)
    time_control: Mapped[TimeControl] = mapped_column(db_enum(TimeControl, "time_control"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Move(CreatedAt, Base):
    __tablename__ = "moves"
    __table_args__ = (
        CheckConstraint("ply >= 1", name="ply_positive"),
        CheckConstraint("uci ~ '^[a-h][1-8][a-h][1-8][qrbn]?$'", name="uci_format"),
        CheckConstraint("length(san) > 0", name="san_nonempty"),
        CheckConstraint(
            "white_remaining_ms >= 0 AND black_remaining_ms >= 0", name="clocks_nonnegative"
        ),
        UniqueConstraint("game_id", "client_request_id", name="uq_moves_game_request"),
    )

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    ply: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[UUID] = mapped_column()
    uci: Mapped[str] = mapped_column(String(5))
    san: Mapped[str] = mapped_column(String(16))
    fen_after: Mapped[str] = mapped_column(String(160))
    white_remaining_ms: Mapped[int] = mapped_column(Integer)
    black_remaining_ms: Mapped[int] = mapped_column(Integer)


class RatingChange(CreatedAt, Base):
    __tablename__ = "rating_changes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "speed"],
            ["user_ratings.user_id", "user_ratings.speed"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("rating_before >= 0 AND rating_after >= 0", name="ratings_nonnegative"),
        Index("ix_rating_changes_user_id", "user_id"),
    )

    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    speed: Mapped[Speed] = mapped_column(db_enum(Speed, "speed"))
    rating_before: Mapped[int] = mapped_column(Integer)
    rating_after: Mapped[int] = mapped_column(Integer)
