"""Shim package: canonical HTTP API surface now lives under platform/http_api.

Backward compat import path: nano_multiagent.server
New platform alias: nano_multiagent.platform.http_api
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
