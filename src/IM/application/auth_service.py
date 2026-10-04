"""Human authentication with durable session rotation and epoch revocation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import secrets

import bcrypt
import jwt

from IM.infra.auth_sessions import AuthSessions
from IM.domain.models import User
from IM.infra.repositories.users import UserAlreadyExistsError
from IM.infra.repositories.users import UserRepository


_ACCESS_TTL_DEFAULT_SECONDS = 15 * 60
_REFRESH_TTL_DEFAULT_SECONDS = 7 * 24 * 60 * 60
_PASSWORD_MIN_LENGTH = 8
_JWT_ALG = "HS256"
# Fixed valid bcrypt input makes an unknown user consume the same bounded work.
_DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxaT4eLQiYxL6vO9eCzH8K9vAWe"


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
        hashed = _DUMMY_HASH
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
        sessions: AuthSessions,
        access_ttl_seconds: int = _ACCESS_TTL_DEFAULT_SECONDS,
        refresh_ttl_seconds: int = _REFRESH_TTL_DEFAULT_SECONDS,
    ) -> None:
        if not jwt_secret:
            raise ValueError("jwt_secret must be non-empty")
        self._users = users
        self._jwt_secret = jwt_secret
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds
        self.sessions = sessions

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
        self.prepare_registration(
            username=username, password=password, display_name=display_name
        )
        return self.complete_registration(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            locale=locale,
        )

    def prepare_registration(
        self, *, username: str, password: str, display_name: str
    ) -> None:
        """Validate registration before spending password computation capacity."""
        if not username.strip():
            raise RegistrationError("username must be non-empty")
        if username.strip() == "system" or username.strip().startswith(
            ("agent:", "shadow:")
        ):
            raise RegistrationError("username uses a reserved runtime identity")
        if not display_name.strip():
            raise RegistrationError("display_name must be non-empty")
        if len(password) < _PASSWORD_MIN_LENGTH:
            raise RegistrationError(
                f"password must be at least {_PASSWORD_MIN_LENGTH} characters"
            )
        if len(password.encode("utf-8")) > 72:
            raise RegistrationError("password must be at most 72 UTF-8 bytes")

    def complete_registration(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str,
        locale: str = "en",
    ) -> TokenPair:
        """Persist a prepared registration and mint its initial session under admission."""
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
        user = self.prepare_login(username=username)
        verified = verify_password(
            password, user.password_hash if user else _DUMMY_HASH
        )
        return self.complete_login(user=user, verified=verified)

    def prepare_login(self, *, username: str) -> User | None:
        """Read the immutable identity/password snapshot before leaving admission."""
        return self._users.get_user_by_username(username=username)

    def complete_login(self, *, user: User | None, verified: bool) -> TokenPair:
        """Recheck the snapshot before issuing a session after password work."""
        fresh = self._users.get_user(user_id=user.id) if user else None
        if (
            not verified
            or user is None
            or fresh is None
            or (
                fresh.password_hash != user.password_hash
                or fresh.auth_epoch != user.auth_epoch
            )
        ):
            raise InvalidCredentialsError("invalid username or password")
        return self._issue_token_pair(fresh)

    @property
    def refresh_ttl_seconds(self) -> int:
        """Return the Cookie lifetime matching persisted refresh expiry."""
        return self._refresh_ttl

    def refresh(self, refresh_token: str) -> TokenPair:
        """Consume one persisted refresh and mint its replacement in the same session."""
        payload = self._decode(refresh_token, expected_type="refresh")
        user = self._users.get_user(user_id=str(payload["sub"]))
        if user is None:
            raise InvalidTokenError("token subject no longer exists")
        return self._issue_token_pair(
            user, session_id=payload["sid"], old_jti=payload["jti"]
        )

    def logout(self, refresh_token: str) -> str:
        """Revoke the entire session and return its identity for socket cleanup."""
        payload = self._decode(refresh_token, expected_type="refresh")
        self.sessions.revoke(payload["sid"])
        return payload["sid"]

    def access_session(self, token: str) -> dict:
        """Validate an access token against the persistent session and human epoch."""
        return self._decode(token, expected_type="access")

    def verify_access_token(self, token: str) -> str:
        """Validate an access token and return its current human identity."""
        return str(self.access_session(token)["sub"])

    def get_user(self, *, user_id: str) -> User | None:
        """Return a user snapshot (used by deps to populate ``current_user``)."""
        return self._users.get_user(user_id=user_id)

    def _issue_token_pair(
        self, user: User, *, session_id: str | None = None, old_jti: str | None = None
    ) -> TokenPair:
        now = datetime.now(timezone.utc)
        expires_at = int((now + timedelta(seconds=self._refresh_ttl)).timestamp())
        refresh_jti = secrets.token_hex(24)
        if session_id is None:
            session_id = self.sessions.create(
                user_id=user.id,
                epoch=user.auth_epoch,
                refresh_jti=refresh_jti,
                expires_at=expires_at,
            )
        elif not self.sessions.rotate(
            session_id=session_id,
            old_jti=old_jti or "",
            new_jti=refresh_jti,
            expires_at=expires_at,
        ):
            raise InvalidTokenError("refresh token already used")
        common = {
            "sub": user.id,
            "sid": session_id,
            "epoch": user.auth_epoch,
            "iat": int(now.timestamp()),
        }
        access_token = jwt.encode(
            {
                **common,
                "type": "access",
                "exp": int((now + timedelta(seconds=self._access_ttl)).timestamp()),
                "jti": secrets.token_hex(16),
            },
            self._jwt_secret,
            algorithm=_JWT_ALG,
        )
        refresh_token = jwt.encode(
            {**common, "type": "refresh", "exp": expires_at, "jti": refresh_jti},
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
        session_id = payload.get("sid")
        epoch = payload.get("epoch")
        if not isinstance(session_id, str) or not isinstance(epoch, int):
            raise InvalidTokenError("token missing session")
        row = self.sessions.valid(session_id, user_id=payload.get("sub"), epoch=epoch)
        if row is None:
            raise InvalidTokenError("session revoked or expired")
        if expected_type == "refresh":
            from IM.infra.auth_sessions import token_digest

            if not secrets.compare_digest(row["refresh_hash"], token_digest(jti)):
                raise InvalidTokenError("refresh token revoked")
        return payload


def resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret from environment or generate a dev-only fallback.

    Returns:
        Secret string from ``IM_JWT_SECRET`` when set; otherwise a stable per-process
        random secret (development convenience — production deployments must set the env).
    """
    configured = os.getenv("IM_JWT_SECRET", "").strip()
    if os.getenv("IM_PUBLIC_MODE") == "1" and len(configured) < 32:
        raise ValueError(
            "public mode requires IM_JWT_SECRET with at least 32 characters"
        )
    if configured:
        return configured
    return secrets.token_urlsafe(32)
