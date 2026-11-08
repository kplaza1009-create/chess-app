import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshSession, Speed, User, UserRating
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RatingResponse,
    RegisterRequest,
    UserResponse,
)
from app.services.security import AuthError, Security, token_hash, utc_now


@dataclass(frozen=True)
class IssuedSession:
    response: AuthResponse
    refresh_token: str
    expires_at: datetime


async def user_response(session: AsyncSession, user: User) -> UserResponse:
    ratings = await session.scalars(
        select(UserRating).where(UserRating.user_id == user.id).order_by(UserRating.speed)
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_key=user.avatar_key,
        created_at=user.created_at,
        ratings=[RatingResponse.model_validate(rating) for rating in ratings],
    )


async def revoke_family(session: AsyncSession, family_id: UUID) -> None:
    await session.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


async def revoke_cookie(session: AsyncSession, security: Security, refresh_token: str) -> None:
    try:
        claims = security.decode(refresh_token, "refresh")
    except AuthError:
        return
    # The original row has id == family_id. Every family mutation locks it first.
    root = await session.scalar(
        select(RefreshSession).where(RefreshSession.id == claims.sid).with_for_update()
    )
    if root is not None and root.user_id == claims.sub:
        row = await session.get(RefreshSession, claims.jti)
        if row is not None and hmac.compare_digest(row.token_hash, token_hash(refresh_token)):
            await revoke_family(session, claims.sid)


async def issue_session(
    session: AsyncSession,
    security: Security,
    user: User,
    family_id: UUID,
    expires_at: datetime,
    refresh_id: UUID,
) -> IssuedSession:
    refresh_token = security.encode(user.id, family_id, "refresh", expires_at, refresh_id)
    session.add(
        RefreshSession(
            id=refresh_id,
            user_id=user.id,
            family_id=family_id,
            token_hash=token_hash(refresh_token),
            expires_at=expires_at,
        )
    )
    now = utc_now().replace(microsecond=0)
    access_expiry = min(now + timedelta(seconds=security.settings.access_token_seconds), expires_at)
    response = AuthResponse(
        access_token=security.encode(user.id, family_id, "access", access_expiry),
        expires_in=int((access_expiry - now).total_seconds()),
        session_id=family_id,
        user=await user_response(session, user),
    )
    return IssuedSession(response, refresh_token, expires_at)


async def start_session(
    session: AsyncSession, security: Security, user: User, old_cookie: str
) -> IssuedSession:
    await revoke_cookie(session, security, old_cookie)
    family_id = uuid4()
    expires = utc_now().replace(microsecond=0) + timedelta(
        days=security.settings.refresh_token_days
    )
    return await issue_session(session, security, user, family_id, expires, family_id)


async def register(
    session: AsyncSession, security: Security, data: RegisterRequest, old_cookie: str
) -> IssuedSession:
    password_hash = await security.hash_password(data.password.get_secret_value())
    try:
        async with session.begin():
            user = User(username=data.username, email=str(data.email), password_hash=password_hash)
            session.add(user)
            await session.flush()
            session.add_all(UserRating(user_id=user.id, speed=speed) for speed in Speed)
            await session.flush()
            issued = await start_session(session, security, user, old_cookie)
        return issued
    except IntegrityError as exc:
        raise AuthError(409, "Unable to register with those details.") from exc


async def login(
    session: AsyncSession, security: Security, data: LoginRequest, old_cookie: str
) -> IssuedSession:
    async with session.begin():
        user = await session.scalar(select(User).where(User.email == str(data.email)))
    encoded_hash = user.password_hash if user is not None else security.dummy_hash
    valid = await security.verify_password(data.password.get_secret_value(), encoded_hash)
    if user is None or not valid or not user.is_active:
        raise AuthError(401, "Incorrect email or password.")
    async with session.begin():
        await session.refresh(user)
        if not user.is_active or user.password_hash != encoded_hash:
            raise AuthError(401, "Incorrect email or password.")
        issued = await start_session(session, security, user, old_cookie)
    return issued


async def refresh(session: AsyncSession, security: Security, refresh_token: str) -> IssuedSession:
    try:
        claims = security.decode(refresh_token, "refresh")
    except AuthError as exc:
        raise AuthError(401, "Please sign in again.", clear_cookie=True) from exc
    issued: IssuedSession | None = None
    async with session.begin():
        root = await session.scalar(
            select(RefreshSession).where(RefreshSession.id == claims.sid).with_for_update()
        )
        if (
            root is None
            or root.user_id != claims.sub
            or root.family_id != claims.sid
            or root.revoked_at is not None
            or root.expires_at <= utc_now()
        ):
            raise AuthError(401, "Please sign in again.", clear_cookie=True)
        row = await session.get(RefreshSession, claims.jti)
        if (
            row is None
            or row.family_id != claims.sid
            or row.user_id != claims.sub
            or not hmac.compare_digest(row.token_hash, token_hash(refresh_token))
        ):
            raise AuthError(401, "Please sign in again.", clear_cookie=True)
        if row.consumed_at is not None or row.revoked_at is not None:
            await revoke_family(session, claims.sid)
        else:
            user = await session.get(User, claims.sub)
            if user is None or not user.is_active:
                await revoke_family(session, claims.sid)
            else:
                row.consumed_at = utc_now()
                issued = await issue_session(
                    session, security, user, claims.sid, root.expires_at, uuid4()
                )
    # Raise after commit so detected reuse actually persists the revocation.
    if issued is None:
        raise AuthError(401, "Please sign in again.", clear_cookie=True)
    return issued


async def logout(session: AsyncSession, security: Security, refresh_token: str) -> None:
    async with session.begin():
        await revoke_cookie(session, security, refresh_token)
