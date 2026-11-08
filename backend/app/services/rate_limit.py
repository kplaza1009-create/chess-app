import math
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.auth_throttle import AuthThrottle
from app.services.security import utc_now


async def enforce_rate_limit(
    session: AsyncSession, key: str, limit: int, window_seconds: int
) -> None:
    now = utc_now()
    expires = now + timedelta(seconds=window_seconds)
    expired = AuthThrottle.expires_at <= now
    statement = (
        insert(AuthThrottle)
        .values(key=key, attempts=1, expires_at=expires)
        .on_conflict_do_update(
            index_elements=[AuthThrottle.key],
            set_={
                "attempts": case((expired, 1), else_=AuthThrottle.attempts + 1),
                "expires_at": case((expired, expires), else_=AuthThrottle.expires_at),
            },
        )
        .returning(AuthThrottle.attempts, AuthThrottle.expires_at)
    )
    async with session.begin():
        attempts, deadline = (await session.execute(statement)).one()
        stale = (
            select(AuthThrottle.key)
            .where(AuthThrottle.expires_at < now - timedelta(days=1))
            .order_by(AuthThrottle.expires_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        await session.execute(delete(AuthThrottle).where(AuthThrottle.key.in_(stale)))
    if attempts > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(max(1, math.ceil((deadline - now).total_seconds())))},
        )
