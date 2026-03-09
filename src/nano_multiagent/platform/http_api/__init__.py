"""Canonical platform-owned HTTP API surface."""

from .app import app, create_app

__all__ = ["app", "create_app"]
