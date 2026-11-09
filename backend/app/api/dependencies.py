from typing import Annotated, cast

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshSession, User
from app.db.session import get_session
from app.services.security import AuthError, Claims, Security

SessionDep = Annotated[AsyncSession, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


def get_security(request: Request) -> Security:
    return cast(Security, request.app.state.security)


SecurityDep = Annotated[Security, Depends(get_security)]


def refresh_cookie(request: Request, security: Security) -> str:
    value = request.cookies.get(security.settings.refresh_cookie_name, "")
    return value if len(value) <= 4096 else ""


def require_csrf(
    request: Request,
    security: SecurityDep,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token", max_length=200)] = None,
) -> None:
    if request.headers.get("origin") not in security.settings.cors_origins:
        raise AuthError(403, "Request origin is not allowed.")
    security.verify_csrf(csrf or "", refresh_cookie(request, security))


async def current_user(
    session: SessionDep,
    security: SecurityDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AuthError(401, "Authentication required")
    claims = security.decode(credentials.credentials, "access")
    return await session_user(session, claims)


async def session_user(session: AsyncSession, claims: Claims) -> User:
    """Revalidate a previously authenticated socket without extending its session."""
    async with session.begin():
        user = await session.scalar(
            select(User)
            .join(RefreshSession, RefreshSession.user_id == User.id)
            .where(
                User.id == claims.sub,
                User.is_active.is_(True),
                RefreshSession.id == claims.sid,
                RefreshSession.family_id == claims.sid,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > func.clock_timestamp(),
            )
        )
    if user is None:
        raise AuthError(401, "Authentication required")
    return user


UserDep = Annotated[User, Depends(current_user)]
