"""Unit tests for IM FastAPI application factory."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.api.routes import messages as message_routes
from IM.api.routes import users as user_routes
from IM.api.routes import web_im
from IM.app import create_app


def test_create_app_registers_im_routes(tmp_path: Path) -> None:
    """Build IM app with required base routes for users and conversations."""
    app = create_app(db_path=tmp_path / "im.db")
    route_paths = {route.path for route in app.routes}

    assert "/im/v1/users" in route_paths
    assert "/im/v1/conversations" in route_paths


def test_create_app_uses_layered_route_modules(tmp_path: Path) -> None:
    """Register routes from api.routes modules instead of inline handlers."""
    app = create_app(db_path=tmp_path / "im.db")

    assert any(route.endpoint is user_routes.create_user for route in app.routes)
    assert any(route.endpoint is web_im.create_conversation for route in app.routes)
    assert any(route.endpoint is message_routes.create_message for route in app.routes)


def test_create_app_allows_local_browser_origins_for_real_im_frontend(tmp_path: Path) -> None:
    """Accept browser preflight requests from localhost/127.0.0.1 frontend origins."""
    app = create_app(db_path=tmp_path / "im.db")

    with TestClient(app) as client:
        response = client.options(
            "/im/v1/users",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert "GET" in response.headers["access-control-allow-methods"]
