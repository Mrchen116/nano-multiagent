"""Authentication helpers for HTTP handlers."""

from fastapi import Request


def extract_bearer_token(authorization: str | None) -> str | None:
    """Parse a bearer token from the `Authorization` header value."""
    if authorization is None:
        return None
    raw_value = authorization.strip()
    if not raw_value:
        return None
    scheme, _, token = raw_value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    stripped_token = token.strip()
    if not stripped_token:
        return None
    return stripped_token


def require_bearer_auth(request: Request) -> None:
    """No-op: authentication is disabled."""
    del request
