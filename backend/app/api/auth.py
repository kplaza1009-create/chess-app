from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import (
    SecurityDep,
    SessionDep,
    UserDep,
    refresh_cookie,
    require_csrf,
)
from app.schemas.auth import (
    AuthResponse,
    CsrfResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.services import auth
from app.services.rate_limit import enforce_rate_limit
from app.services.security import Security, utc_now

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, security: Security, issued: auth.IssuedSession) -> None:
    response.set_cookie(
        key=security.settings.refresh_cookie_name,
        value=issued.refresh_token,
        max_age=max(0, int((issued.expires_at - utc_now()).total_seconds())),
        expires=issued.expires_at,
        path="/",
        secure=security.settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response, security: Security) -> None:
    response.delete_cookie(
        security.settings.refresh_cookie_name,
        path="/",
        secure=security.settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def client_key(request: Request, security: Security, scope: str) -> str:
    address = request.client.host if request.client else "unknown"
    return security.throttle_key(scope, address)


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(request: Request, security: SecurityDep) -> CsrfResponse:
    return CsrfResponse(csrf_token=security.csrf_token(refresh_cookie(request, security)))


@router.post(
    "/register", response_model=AuthResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    security: SecurityDep,
) -> AuthResponse:
    await enforce_rate_limit(session, client_key(request, security, "register"), 10, 3600)
    issued = await auth.register(session, security, data, refresh_cookie(request, security))
    set_refresh_cookie(response, security, issued)
    return issued.response


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(require_csrf)])
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    security: SecurityDep,
) -> AuthResponse:
    await enforce_rate_limit(session, client_key(request, security, "login"), 30, 60)
    await enforce_rate_limit(session, security.throttle_key("email", str(data.email)), 10, 300)
    issued = await auth.login(session, security, data, refresh_cookie(request, security))
    set_refresh_cookie(response, security, issued)
    return issued.response


@router.post("/refresh", response_model=AuthResponse, dependencies=[Depends(require_csrf)])
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    security: SecurityDep,
) -> AuthResponse:
    await enforce_rate_limit(session, client_key(request, security, "refresh"), 120, 60)
    issued = await auth.refresh(session, security, refresh_cookie(request, security))
    set_refresh_cookie(response, security, issued)
    return issued.response


@router.post("/logout", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    security: SecurityDep,
) -> MessageResponse:
    await auth.logout(session, security, refresh_cookie(request, security))
    clear_refresh_cookie(response, security)
    return MessageResponse(message="Signed out")


@router.get("/me", response_model=UserResponse)
async def me(user: UserDep, session: SessionDep) -> UserResponse:
    async with session.begin():
        return await auth.user_response(session, user)
