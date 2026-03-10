"""Verify platform/http_api is the canonical home for the HTTP API app and routes."""

from nano_multiagent.platform.http_api import create_app
from nano_multiagent.platform.http_api.app import app, create_app as platform_create_app
from nano_multiagent.platform.http_api.routes.event import (
    router as platform_event_router,
)
from nano_multiagent.platform.http_api.routes.session import (
    router as platform_session_router,
)
from nano_multiagent.server import app as legacy_app_module
from nano_multiagent.server import create_app as legacy_create_app
from nano_multiagent.server.app import app as legacy_app
from nano_multiagent.server.routes.event import router as legacy_event_router
from nano_multiagent.server.routes.session import router as legacy_session_router


def test_platform_http_api_is_canonical_home() -> None:
    """Platform HTTP API exports must originate from platform-owned modules."""
    assert create_app.__module__ == "nano_multiagent.platform.http_api.app"
    assert app.__module__ == "fastapi.applications"
    assert platform_event_router.__module__ == "nano_multiagent.platform.http_api.routes.event"
    assert platform_session_router.__module__ == "nano_multiagent.platform.http_api.routes.session"


def test_old_server_paths_are_compat_shims() -> None:
    """Legacy server modules must re-export canonical platform HTTP API objects."""
    assert legacy_create_app is create_app
    assert legacy_create_app is platform_create_app
    assert legacy_app is app
    assert legacy_app_module.app is app
    assert legacy_app_module.create_app is create_app
    assert legacy_event_router is platform_event_router
    assert legacy_session_router is platform_session_router
