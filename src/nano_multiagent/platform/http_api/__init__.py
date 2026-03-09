"""Platform HTTP API surface re-exported from canonical server package."""

from nano_multiagent.server.app import app, create_app  # noqa: F401

__all__ = ["app", "create_app"]
