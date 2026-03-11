"""Verify platform/http_api is the canonical home for the HTTP API app surface."""

from importlib.util import find_spec

from agent.platform.http_api import create_app
from agent.platform.http_api.app import app, create_app as platform_create_app
from agent.platform.http_api.routes.event import router as platform_event_router
from agent.platform.http_api.routes.session import router as platform_session_router



def test_platform_http_api_is_canonical_home() -> None:
    """Platform HTTP API exports must originate from platform-owned modules."""
    assert create_app.__module__ == "agent.platform.http_api.app"
    assert app.__module__ == "fastapi.applications"
    assert platform_create_app.__module__ == "agent.platform.http_api.app"
    assert platform_event_router.__module__ == "agent.platform.http_api.routes.event"
    assert platform_session_router.__module__ == "agent.platform.http_api.routes.session"



def test_legacy_server_root_is_removed() -> None:
    assert find_spec("agent.server") is None
