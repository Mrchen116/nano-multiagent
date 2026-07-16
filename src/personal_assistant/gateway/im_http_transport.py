"""Normalize shared HTTP transport values for IM-facing Gateway adapters."""

from __future__ import annotations

from urllib.parse import urlparse


def build_im_http_headers(token: str | None) -> dict[str, str]:
    """Build the shared Gateway bootstrap headers for an IM HTTP request.

    Args:
        token: Optional IM bearer token. ``None`` omits authorization.

    Returns:
        A fresh header mapping with the Gateway bootstrap identity and optional auth.
    """

    headers = {"User-Agent": "nano-multiagent-gateway-bootstrap"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def normalize_im_http_base_url(url: str) -> str:
    """Normalize an IM HTTP or WebSocket URL for HTTP adapter use.

    Args:
        url: Configured IM endpoint using an HTTP(S) or WebSocket scheme.

    Returns:
        HTTP(S) URL with an equivalent authority/path and no trailing slash.

    Raises:
        ValueError: When the configured scheme is not HTTP(S) or WebSocket.
    """

    parsed = urlparse(url)
    if parsed.scheme == "http":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "ws":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "wss":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    raise ValueError("IM URL must use http(s) or ws(s)")


__all__ = ["build_im_http_headers", "normalize_im_http_base_url"]
