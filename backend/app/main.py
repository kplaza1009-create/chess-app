import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import clear_refresh_cookie
from app.api.auth import router as auth_router
from app.api.board import router as board_router
from app.config import Settings, get_settings
from app.db.session import Database, get_session
from app.middleware import SecurityHeadersMiddleware
from app.services.security import AuthError, Security

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(settings)
        application.state.database = database
        try:
            security = Security(settings)
            await security.initialize()
            application.state.security = security
            yield
        finally:
            await database.close()

    application = FastAPI(
        title="Chess API",
        version="0.2.1",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.app_env == "production" else "/openapi.json",
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    application.include_router(auth_router)
    application.include_router(board_router)

    @application.exception_handler(AuthError)
    async def authentication_error(request: Request, exc: AuthError) -> JSONResponse:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status)
        if exc.status == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        if exc.clear_cookie:
            clear_refresh_cookie(response, request.app.state.security)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's default errors include input values, including passwords.
        errors = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.warning("Database operation failed (%s)", type(exc).__name__)
        return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)

    @application.get("/health/live", response_model=HealthResponse, tags=["health"])
    async def live() -> HealthResponse:
        return HealthResponse()

    @application.get("/health/ready", response_model=HealthResponse, tags=["health"])
    async def ready(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> HealthResponse:
        try:
            async with asyncio.timeout(3):
                await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, TimeoutError) as exc:
            logger.warning("Database readiness check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc
        return HealthResponse()

    return application
