"""Shim: platform/http_api/app re-exports canonical server.app surface."""

from nano_multiagent.server.app import app, create_app  # noqa: F401

__all__ = ["app", "create_app"]
