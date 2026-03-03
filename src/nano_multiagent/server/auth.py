"""Authentication helpers for HTTP handlers."""

from fastapi import Request, status

from .deps import APIError


def extract_bearer_token(authorization: str | None) -> str | None:
    """Parse a bearer token from the `Authorization` header value.

    Args:
        authorization: Raw request header value.

    Returns:
        Token string when header uses `Bearer <token>` format, otherwise `None`.
    """
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


def require_bearer_auth(request: Request) -> str:
    """Enforce bearer-token authentication for protected HTTP routes.

    Args:
        request: Incoming FastAPI request object.

    Returns:
        Validated bearer token value.

    Raises:
        APIError: When token is missing/invalid, mapped to HTTP 401.
    """
    token = extract_bearer_token(request.headers.get("Authorization"))
    if token is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="missing or invalid bearer token",
            retryable=False,
        )

    expected_token = getattr(request.app.state, "auth_token", None)
    if expected_token and token != expected_token:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="invalid bearer token",
            retryable=False,
        )
    return token
