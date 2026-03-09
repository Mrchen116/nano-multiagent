"""Compatibility shim for the canonical platform HTTP API auth helpers."""

from nano_multiagent.platform.http_api.auth import extract_bearer_token, require_bearer_auth

__all__ = ["extract_bearer_token", "require_bearer_auth"]
