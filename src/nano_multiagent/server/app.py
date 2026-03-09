"""Compatibility shim for the canonical platform HTTP API app module."""

from nano_multiagent.platform.http_api.app import app, create_app

__all__ = ["app", "create_app"]
