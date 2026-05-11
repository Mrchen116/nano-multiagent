"""Authentication HTTP routes: register, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import current_user, get_auth_service
from IM.application.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    RegistrationError,
    TokenPair,
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


class TokenPairResponse(BaseModel):
    """Token pair envelope returned by register/login/refresh."""

    access_token: str
    refresh_token: str
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
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


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
    )


def _to_pair_response(pair: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        user=_to_user_response(pair.user),
    )


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    """Create a new user with credentials and return an initial token pair."""
    try:
        pair = service.register(
            username=payload.username.strip(),
            password=payload.password,
            display_name=payload.display_name.strip(),
            locale=payload.locale.strip() or "en",
        )
    except RegistrationError as exc:
        detail = str(exc)
        code = status.HTTP_409_CONFLICT if "exists" in detail else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=detail) from exc
    return _to_pair_response(pair)


@router.post("/login", response_model=TokenPairResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    """Verify credentials and return a fresh token pair."""
    try:
        pair = service.login(username=payload.username.strip(), password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials") from exc
    return _to_pair_response(pair)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    """Rotate the refresh token: mint a new pair and revoke the prior refresh jti."""
    try:
        pair = service.refresh(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _to_pair_response(pair)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    """Revoke the supplied refresh token."""
    try:
        service.logout(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LogoutResponse(ok=True)


@router.get("/me", response_model=AuthUserResponse)
def get_me(user: User = Depends(current_user)) -> AuthUserResponse:
    """Return the currently authenticated user from the Bearer token."""
    return _to_user_response(user)
