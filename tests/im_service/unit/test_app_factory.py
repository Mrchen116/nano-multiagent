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


def test_create_app_redirects_frontend_routes_to_dev_server_when_dist_is_missing(tmp_path: Path) -> None:
    """Redirect discoverable Web IM routes to the configured dev server when no build exists."""
    app = create_app(
        db_path=tmp_path / "im.db",
        frontend_dist_dir=tmp_path / "missing-dist",
        frontend_dev_base_url="http://127.0.0.1:4173",
    )

    with TestClient(app) as client:
        root_response = client.get("/", follow_redirects=False)
        chat_response = client.get("/chat", follow_redirects=False)
        settings_response = client.get("/settings/agents", follow_redirects=False)
        bind_response = client.get("/bind/confirm?token=test-token", follow_redirects=False)

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "http://127.0.0.1:4173/"
    assert chat_response.status_code == 307
    assert chat_response.headers["location"] == "http://127.0.0.1:4173/chat"
    assert settings_response.status_code == 307
    assert settings_response.headers["location"] == "http://127.0.0.1:4173/settings/agents"
    assert bind_response.status_code == 307
    assert bind_response.headers["location"] == "http://127.0.0.1:4173/bind/confirm?token=test-token"


def test_create_app_serves_built_frontend_shell_on_im_routes(tmp_path: Path) -> None:
    """Serve the built SPA shell from the IM service host when dist assets exist."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<!doctype html><title>IM shell</title>", encoding="utf-8")
    (dist_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")

    app = create_app(
        db_path=tmp_path / "im.db",
        frontend_dist_dir=dist_dir,
        frontend_dev_base_url="http://127.0.0.1:4173",
    )

    with TestClient(app) as client:
        root_response = client.get("/")
        chat_response = client.get("/chat")
        settings_response = client.get("/settings/agents")
        bind_response = client.get("/bind/confirm?token=test-token")
        favicon_response = client.get("/favicon.svg")

    assert root_response.status_code == 200
    assert root_response.text == "<!doctype html><title>IM shell</title>"
    assert chat_response.status_code == 200
    assert chat_response.text == "<!doctype html><title>IM shell</title>"
    assert settings_response.status_code == 200
    assert settings_response.text == "<!doctype html><title>IM shell</title>"
    assert bind_response.status_code == 200
    assert bind_response.text == "<!doctype html><title>IM shell</title>"
    assert favicon_response.status_code == 200
    assert favicon_response.text == "<svg></svg>"
