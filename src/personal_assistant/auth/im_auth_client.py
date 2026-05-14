"""Async HTTP client for IM authentication: token refresh and credential login.

Encapsulates the two auth endpoints the Gateway needs to stay connected after an
access-token expires:

1. ``POST /im/v1/auth/refresh`` — exchange a long-lived refresh token for a new
   access/refresh token pair (IM supports token rotation).
2. ``POST /im/v1/auth/login`` — fall back to full credential auth when the refresh
   token itself has expired or been revoked.

The client is intentionally thin: it performs the HTTP call, validates the response
shape, and raises ``IMAuthError`` on any failure so callers can branch on auth vs.
network errors without parsing HTTP status codes themselves.
"""
from __future__ import annotations

import httpx


class IMAuthError(Exception):
    """Raised when an IM auth operation fails (bad credentials, expired token, etc.).

    Args:
        message: Human-readable failure description.
        status_code: HTTP status code returned by IM, or None for network-level failures.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IMAuthClient:
    """Async HTTP client for IM token refresh and credential login.

    Args:
        base_url: HTTP base URL of the IM service (e.g. ``http://localhost:8011``).
        timeout_seconds: Per-request timeout.
        transport: Optional httpx transport override (used in tests).
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Exchange a refresh token for a new access/refresh token pair.

        Args:
            refresh_token: The long-lived refresh token to exchange.

        Returns:
            Tuple of ``(access_token, refresh_token)`` from the IM response.

        Raises:
            IMAuthError: When IM rejects the token (expired, revoked) or returns an
                unexpected response shape.
        """
        async with self._make_client() as client:
            try:
                response = await client.post(
                    f"{self._base_url}/im/v1/auth/refresh",
                    json={"refresh_token": refresh_token},
                )
            except httpx.HTTPError as exc:
                raise IMAuthError(f"network error during token refresh: {exc}") from exc
        return self._extract_token_pair(response, operation="refresh")

    async def login(self, *, username: str, password: str) -> tuple[str, str]:
        """Authenticate with username and password, returning a new token pair.

        Args:
            username: IM account username.
            password: IM account password.

        Returns:
            Tuple of ``(access_token, refresh_token)`` from the IM response.

        Raises:
            IMAuthError: When IM rejects the credentials or returns an unexpected shape.
        """
        async with self._make_client() as client:
            try:
                response = await client.post(
                    f"{self._base_url}/im/v1/auth/login",
                    json={"username": username, "password": password},
                )
            except httpx.HTTPError as exc:
                raise IMAuthError(f"network error during login: {exc}") from exc
        return self._extract_token_pair(response, operation="login")

    def _make_client(self) -> httpx.AsyncClient:
        kwargs: dict = {
            "timeout": self._timeout,
            "trust_env": False,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _extract_token_pair(response: httpx.Response, *, operation: str) -> tuple[str, str]:
        if response.status_code != 200:
            raise IMAuthError(
                f"IM {operation} failed with status {response.status_code}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except Exception as exc:
            raise IMAuthError(f"IM {operation} returned non-JSON response") from exc
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not isinstance(access, str) or not access:
            raise IMAuthError(f"IM {operation} response missing access_token")
        if not isinstance(refresh, str) or not refresh:
            raise IMAuthError(f"IM {operation} response missing refresh_token")
        return access, refresh
