"""Verify platform/http_api is the canonical home for the HTTP API app surface."""

import nano_multiagent.server as legacy_server
from nano_multiagent.platform.http_api import create_app
from nano_multiagent.platform.http_api.app import app, create_app as platform_create_app
from nano_multiagent.platform.http_api.routes.event import router as platform_event_router
from nano_multiagent.platform.http_api.routes.session import router as platform_session_router
from nano_multiagent.server.app import app as legacy_app


def test_platform_http_api_is_canonical_home() -> None:
    """Platform HTTP API exports must originate from platform-owned modules."""
    assert create_app.__module__ == "nano_multiagent.platform.http_api.app"
    assert app.__module__ == "fastapi.applications"
    assert platform_event_router.__module__ == "nano_multiagent.platform.http_api.routes.event"
    assert platform_session_router.__module__ == "nano_multiagent.platform.http_api.routes.session"



def test_surviving_server_entrypoints_are_compat_shims() -> None:
    """Only the legacy server package root and app entrypoint should survive in M87."""
    assert legacy_server.create_app is create_app
    assert legacy_server.create_app is platform_create_app
    assert legacy_server.app.__name__ == "nano_multiagent.server.app"
    assert legacy_app is app
    assert legacy_server.app.app is app
    assert legacy_server.app.create_app is create_app
    assert legacy_server.app.create_app is platform_create_app
