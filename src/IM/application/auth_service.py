"""Authentication application service: register, login, refresh, logout, verify.

Notes:
    The service is the single source of truth for JWT signing and refresh-token rotation.
    Refresh-token reuse (after a successful refresh or an explicit logout) is rejected via
    an in-memory blacklist keyed by JWT id (``jti``). The blacklist is intentionally process-local:
    the IM service runs as a single FastAPI app instance, and a restart invalidates all outstanding
    refresh tokens — acceptable for the development-stage scope of feat-340.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import secrets
from threading import Lock

import bcrypt
import jwt

from IM.domain.models import User
from IM.infra.repositories import UserAlreadyExistsError, UserRepository


_ACCESS_TTL_DEFAULT_SECONDS = 15 * 60
_REFRESH_TTL_DEFAULT_SECONDS = 7 * 24 * 60 * 60
_PASSWORD_MIN_LENGTH = 8
_JWT_ALG = "HS256"


class AuthError(ValueError):
    """Base error raised by auth flows for HTTP layer translation."""


class RegistrationError(AuthError):
    """Raised when registration cannot proceed (duplicate username, weak password)."""


class InvalidCredentialsError(AuthError):
    """Raised when login fails for any reason (unknown user or wrong password)."""


class InvalidTokenError(AuthError):
    """Raised when a token is malformed, expired, revoked, or has the wrong type."""


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Result of register / login / refresh."""

    access_token: str
    refresh_token: str
    user: User


def hash_password(plain: str) -> str:
    """Return a bcrypt hash for the plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Returns ``False`` (never raises) when the hash is missing or malformed —
    callers translate to InvalidCredentialsError without leaking which branch
    failed (avoid existence-oracle leakage between unknown-user and wrong-password).
    """
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


class AuthService:
    """Coordinate registration, login, refresh-token rotation, and JWT verification."""

    def __init__(
        self,
        *,
        users: UserRepository,
        jwt_secret: str,
        access_ttl_seconds: int = _ACCESS_TTL_DEFAULT_SECONDS,
        refresh_ttl_seconds: int = _REFRESH_TTL_DEFAULT_SECONDS,
    ) -> None:
        if not jwt_secret:
            raise ValueError("jwt_secret must be non-empty")
        self._users = users
        self._jwt_secret = jwt_secret
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds
        # Blacklist of revoked refresh-token jti values; in-memory, process-local.
        self._revoked_jti: set[str] = set()
        self._lock = Lock()

    def register(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        locale: str = "en",
    ) -> TokenPair:
        """Create a user with credentials and return an initial token pair.

        Raises:
            RegistrationError: when username already exists, fields are blank,
                or password fails the minimum-length check.
        """
        if not username.strip():
            raise RegistrationError("username must be non-empty")
        if not display_name.strip():
            raise RegistrationError("display_name must be non-empty")
        if len(password) < _PASSWORD_MIN_LENGTH:
            raise RegistrationError(
                f"password must be at least {_PASSWORD_MIN_LENGTH} characters"
            )
        password_hash = hash_password(password)
        try:
            user = self._users.create_user(
                username=username,
                display_name=display_name,
                password_hash=password_hash,
                locale=locale,
            )
        except UserAlreadyExistsError as exc:
            raise RegistrationError("username already exists") from exc
        return self._issue_token_pair(user)

    def login(self, *, username: str, password: str) -> TokenPair:
        """Verify credentials and return a fresh token pair.

        Raises:
            InvalidCredentialsError: for unknown username or wrong password
                — same error type for both to avoid leaking which side failed.
        """
        user = self._users.get_user_by_username(username=username)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("invalid username or password")
        return self._issue_token_pair(user)

    def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token: mint new pair, revoke old refresh token."""
        payload = self._decode(refresh_token, expected_type="refresh")
        user_id = str(payload["sub"])
        user = self._users.get_user(user_id=user_id)
        if user is None:
            raise InvalidTokenError("token subject no longer exists")
        # Atomically revoke the old jti before issuing the new pair so a parallel
        # refresh cannot reuse the same token twice.
        jti = str(payload["jti"])
        with self._lock:
            if jti in self._revoked_jti:
                raise InvalidTokenError("refresh token already used")
            self._revoked_jti.add(jti)
        return self._issue_token_pair(user)

    def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token without minting a new pair."""
        payload = self._decode(refresh_token, expected_type="refresh")
        with self._lock:
            self._revoked_jti.add(str(payload["jti"]))

    def verify_access_token(self, token: str) -> str:
        """Decode and validate an access token; return the user id."""
        payload = self._decode(token, expected_type="access")
        return str(payload["sub"])

    def get_user(self, *, user_id: str) -> User | None:
        """Return a user snapshot (used by deps to populate ``current_user``)."""
        return self._users.get_user(user_id=user_id)

    def _issue_token_pair(self, user: User) -> TokenPair:
        now = datetime.now(timezone.utc)
        access_token = jwt.encode(
            {
                "sub": user.id,
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=self._access_ttl)).timestamp()),
                "jti": secrets.token_hex(16),
            },
            self._jwt_secret,
            algorithm=_JWT_ALG,
        )
        refresh_token = jwt.encode(
            {
                "sub": user.id,
                "type": "refresh",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=self._refresh_ttl)).timestamp()),
                "jti": secrets.token_hex(16),
            },
            self._jwt_secret,
            algorithm=_JWT_ALG,
        )
        return TokenPair(
            access_token=access_token, refresh_token=refresh_token, user=user
        )

    def _decode(self, token: str, *, expected_type: str) -> dict:
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=[_JWT_ALG])
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("invalid token") from exc
        if payload.get("type") != expected_type:
            raise InvalidTokenError(f"expected {expected_type} token")
        jti = payload.get("jti")
        if not isinstance(jti, str):
            raise InvalidTokenError("token missing jti")
        if expected_type == "refresh":
            with self._lock:
                if jti in self._revoked_jti:
                    raise InvalidTokenError("refresh token revoked")
        return payload


def resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret from environment or generate a dev-only fallback.

    Returns:
        Secret string from ``IM_JWT_SECRET`` when set; otherwise a stable per-process
        random secret (development convenience — production deployments must set the env).
    """
    configured = os.getenv("IM_JWT_SECRET", "").strip()
    if configured:
        return configured
    return secrets.token_urlsafe(32)
