"""Authentication HTTP routes: register, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from urllib.parse import urlsplit

from IM.api.public_boundary import client_source
from pydantic import BaseModel, Field

from IM.api.deps import (
    authenticated_user,
    current_user,
    get_auth_service,
    _extract_bearer_token,
)
from IM.application.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    RegistrationError,
    TokenPair,
    hash_password,
    verify_password,
)
from IM.domain.models import User


router = APIRouter(tags=["auth"], prefix="/im/v1/auth")


class AuthUserResponse(BaseModel):
    """Public user payload returned by auth endpoints (never includes password_hash)."""

    id: str
    username: str
    display_name: str
    owner_id: str
    locale: str
    default_entry_node_id: str | None = None
    owned_node_ids: list[str] = Field(default_factory=list)
    created_at: str = ""
    membership_status: str
    is_company_admin: bool


class TokenPairResponse(BaseModel):
    """Token pair envelope returned by register/login/refresh."""

    access_token: str
    refresh_token: str
    user: AuthUserResponse


class BrowserSessionResponse(BaseModel):
    """Browser-readable session; the refresh credential travels only by Cookie."""

    access_token: str
    user: AuthUserResponse


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)
    locale: str = Field(default="en", max_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class LogoutResponse(BaseModel):
    ok: bool = True


def _to_user_response(user: User) -> AuthUserResponse:
    """Convert a domain user into the auth-public payload (no password_hash)."""
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        owner_id=user.owner_id,
        locale=user.locale,
        default_entry_node_id=user.default_entry_node_id,
        owned_node_ids=user.owned_node_ids,
        created_at=user.created_at,
        membership_status=user.membership_status,
        is_company_admin=user.is_company_admin,
    )


def _to_pair_response(pair: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        user=_to_user_response(pair.user),
    )


def _browser(request: Request) -> bool:
    return request.headers.get("X-IM-Session") == "browser"


def _session_response(
    pair: TokenPair, request: Request, response: Response, service: AuthService
):
    response.headers["Cache-Control"] = "no-store"
    if not _browser(request):
        return _to_pair_response(pair)
    response.set_cookie(
        "im_refresh",
        pair.refresh_token,
        max_age=service.refresh_ttl_seconds,
        httponly=True,
        secure=urlsplit(request.app.state.public_url).scheme == "https",
        samesite="strict",
        path="/",
    )
    return BrowserSessionResponse(
        access_token=pair.access_token, user=_to_user_response(pair.user)
    )


def _refresh_credential(
    request: Request, payload: RefreshRequest | LogoutRequest
) -> str | None:
    if _browser(request):
        if payload.refresh_token is not None:
            raise HTTPException(
                status_code=422, detail="browser session uses Cookie only"
            )
        return request.cookies.get("im_refresh")
    if not payload.refresh_token:
        raise HTTPException(status_code=422, detail="refresh_token is required")
    return payload.refresh_token


@router.post(
    "/register",
    response_model=TokenPairResponse | BrowserSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Create a new user with credentials and return the selected session transport."""
    username, display_name = payload.username.strip(), payload.display_name.strip()
    try:
        service.prepare_registration(
            username=username, password=payload.password, display_name=display_name
        )
        hashed = await request.app.state.password_work.run(
            hash_password, payload.password
        )
        pair = service.complete_registration(
            username=username,
            password_hash=hashed,
            display_name=display_name,
            locale=payload.locale.strip() or "en",
        )
    except RegistrationError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if "exists" in detail else 422, detail=detail
        ) from exc
    return _session_response(pair, request, response, service)


@router.post("/login", response_model=TokenPairResponse | BrowserSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Verify credentials with bounded CPU work and source/account failure isolation."""
    account = payload.username.strip().casefold()
    source_account = "login:failure:" + client_source(request.scope) + ":" + account
    limits = request.app.state.auth_limits
    limits.check(source_account, limit=10, window=900, consume=False)
    limits.check("login:target:" + account, limit=1, window=1)
    user = service.prepare_login(username=payload.username.strip())
    verified = await request.app.state.password_work.run(
        verify_password, payload.password, user.password_hash if user else None
    )
    try:
        pair = service.complete_login(user=user, verified=verified)
    except InvalidCredentialsError as exc:
        limits.check(source_account, limit=10, window=900)
        raise HTTPException(status_code=401, detail="invalid credentials") from exc
    limits.clear(source_account)
    return _session_response(pair, request, response, service)


@router.post("/refresh", response_model=TokenPairResponse | BrowserSessionResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Rotate the explicit program credential or an Origin-checked browser Cookie."""
    credential = _refresh_credential(request, payload)
    if not credential:
        raise HTTPException(status_code=401, detail="missing refresh cookie")
    request.app.state.auth_limits.check(
        "refresh:credential:" + credential, limit=20, window=60
    )
    try:
        pair = service.refresh(credential)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _session_response(pair, request, response, service)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    """Revoke a session; browser logout also expires its HttpOnly Cookie."""
    credential = _refresh_credential(request, payload)
    try:
        if credential:
            session_id = service.logout(credential)
            await request.app.state.user_stream_registry.close_session(session_id)
    except InvalidTokenError as exc:
        if not _browser(request):
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    if _browser(request):
        response.delete_cookie(
            "im_refresh",
            path="/",
            httponly=True,
            samesite="strict",
            secure=urlsplit(request.app.state.public_url).scheme == "https",
        )
    return LogoutResponse(ok=True)


@router.get("/me", response_model=AuthUserResponse)
def get_me(user: User = Depends(authenticated_user)) -> AuthUserResponse:
    """Return the currently authenticated user from the Bearer token."""
    return _to_user_response(user)


@router.post("/ws-ticket")
def websocket_ticket(
    request: Request,
    user: User = Depends(current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Exchange Bearer authentication for a short-lived single-use browser ticket."""
    session = service.access_session(_extract_bearer_token(request))
    request.app.state.auth_limits.check(
        "ws-ticket:" + session["sid"], limit=10, window=60
    )
    return {"ticket": service.sessions.issue_ticket(session["sid"]), "expires_in": 30}
