"""Unit tests for IM FastAPI application factory."""

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from IM.api.routes import auth as auth_routes
from IM.api.routes import messages as message_routes
from IM.api.routes import web_im
from IM.app import _resolve_frontend_dist_candidates, create_app

from ._route_introspection import walk_routes


def test_resolve_frontend_dist_candidates_keeps_repo_dist_as_runtime_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    """Keep the current repo dist in the lookup chain even when a stale worktree path is configured."""
    explicit_stale_dir = tmp_path / "missing-explicit-dist"
    env_stale_dir = tmp_path / "missing-env-dist"
    monkeypatch.setenv("IM_FRONTEND_DIST_DIR", str(env_stale_dir))

    candidates = _resolve_frontend_dist_candidates(explicit_stale_dir)

    assert candidates[0] == explicit_stale_dir.resolve(strict=False)
    assert candidates[1] == env_stale_dir.resolve(strict=False)
    assert any(
        candidate.name == "dist" and candidate.is_absolute()
        for candidate in candidates[2:]
    )
    assert any(
        str(candidate).endswith("/src/IM/frontend/dist") for candidate in candidates[2:]
    )


def test_create_app_registers_im_routes(tmp_path: Path) -> None:
    """Build IM app with required base routes for auth and conversations (post feat-340-M1)."""
    app = create_app(db_path=tmp_path / "im.db")
    route_paths = {
        route.path for route in walk_routes(app.routes) if hasattr(route, "path")
    }

    assert "/im/v1/auth/register" in route_paths
    assert "/im/v1/conversations" in route_paths


def test_create_app_uses_layered_route_modules(tmp_path: Path) -> None:
    """Register routes from api.routes modules instead of inline handlers."""
    app = create_app(db_path=tmp_path / "im.db")

    routes = list(walk_routes(app.routes))
    assert any(
        getattr(route, "endpoint", None) is auth_routes.register for route in routes
    )
    assert any(
        getattr(route, "endpoint", None) is web_im.create_conversation
        for route in routes
    )
    assert any(
        getattr(route, "endpoint", None) is message_routes.create_message
        for route in routes
    )


def test_create_app_allows_local_browser_origins_for_real_im_frontend(
    tmp_path: Path,
) -> None:
    """Accept browser preflight requests from localhost/127.0.0.1 frontend origins."""
    app = create_app(db_path=tmp_path / "im.db")

    with TestClient(app) as client:
        response = client.options(
            "/im/v1/auth/register",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_create_app_redirects_frontend_routes_to_dev_server_when_dist_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Redirect discoverable Web IM routes to the configured dev server when no build exists."""
    missing_dist_dir = tmp_path / "missing-dist"
    monkeypatch.setattr(
        "IM.app._resolve_frontend_dist_candidates",
        lambda frontend_dist_dir: (missing_dist_dir,),
    )

    app = create_app(
        db_path=tmp_path / "im.db",
        frontend_dist_dir=missing_dist_dir,
        frontend_dev_base_url="http://127.0.0.1:4173",
    )

    with TestClient(app) as client:
        root_response = client.get("/", follow_redirects=False)
        chat_response = client.get("/chat", follow_redirects=False)
        settings_response = client.get("/settings/agents", follow_redirects=False)
        bind_response = client.get(
            "/bind/confirm?token=test-token", follow_redirects=False
        )

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "http://127.0.0.1:4173/"
    assert chat_response.status_code == 307
    assert chat_response.headers["location"] == "http://127.0.0.1:4173/chat"
    assert settings_response.status_code == 307
    assert (
        settings_response.headers["location"] == "http://127.0.0.1:4173/settings/agents"
    )
    assert bind_response.status_code == 307
    assert (
        bind_response.headers["location"]
        == "http://127.0.0.1:4173/bind/confirm?token=test-token"
    )


def test_create_app_falls_back_to_secondary_frontend_dist_when_primary_worktree_dist_disappears(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Serve the next valid frontend build when the original worktree dist is removed after startup."""
    stale_dist_dir = tmp_path / "stale-dist"
    stale_dist_dir.mkdir()
    (stale_dist_dir / "index.html").write_text(
        "<!doctype html><title>stale shell</title>", encoding="utf-8"
    )

    fallback_dist_dir = tmp_path / "fallback-dist"
    fallback_assets_dir = fallback_dist_dir / "assets"
    fallback_assets_dir.mkdir(parents=True)
    (fallback_dist_dir / "index.html").write_text(
        "<!doctype html><title>fallback shell</title>", encoding="utf-8"
    )
    (fallback_dist_dir / "favicon.svg").write_text(
        "<svg>fallback</svg>", encoding="utf-8"
    )
    (fallback_assets_dir / "app.js").write_text(
        "console.log('fallback asset');", encoding="utf-8"
    )

    monkeypatch.setattr(
        "IM.app._resolve_frontend_dist_candidates",
        lambda frontend_dist_dir: (stale_dist_dir, fallback_dist_dir),
    )

    app = create_app(
        db_path=tmp_path / "im.db",
        frontend_dist_dir=stale_dist_dir,
        frontend_dev_base_url="http://127.0.0.1:4173",
    )

    shutil.rmtree(stale_dist_dir)

    with TestClient(app) as client:
        root_response = client.get("/")
        chat_response = client.get("/chat")
        favicon_response = client.get("/favicon.svg")
        asset_response = client.get("/assets/app.js")

    assert root_response.status_code == 200
    assert root_response.text == "<!doctype html><title>fallback shell</title>"
    assert chat_response.status_code == 200
    assert chat_response.text == "<!doctype html><title>fallback shell</title>"
    assert favicon_response.status_code == 200
    assert favicon_response.text == "<svg>fallback</svg>"
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log('fallback asset');"


def test_create_app_serves_built_frontend_shell_on_im_routes(tmp_path: Path) -> None:
    """Serve the built SPA shell from the IM service host when dist assets exist."""
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><title>IM shell</title>", encoding="utf-8"
    )
    (dist_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('IM shell');", encoding="utf-8")

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
        asset_response = client.get("/assets/app.js")

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
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log('IM shell');"


def test_create_app_serves_spa_shell_on_login_register_me_routes(
    tmp_path: Path,
) -> None:
    """SPA routes /login /register /me must return the index.html shell, not a 404."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><title>IM shell</title>", encoding="utf-8"
    )

    app = create_app(
        db_path=tmp_path / "im.db",
        frontend_dist_dir=dist_dir,
        frontend_dev_base_url="http://127.0.0.1:4173",
    )

    with TestClient(app) as client:
        login_response = client.get("/login")
        register_response = client.get("/register")
        me_response = client.get("/me")

    assert login_response.status_code == 200, "/login must serve SPA shell, not 404"
    assert login_response.text == "<!doctype html><title>IM shell</title>"
    assert register_response.status_code == 200, (
        "/register must serve SPA shell, not 404"
    )
    assert register_response.text == "<!doctype html><title>IM shell</title>"
    assert me_response.status_code == 200, "/me must serve SPA shell, not 404"
    assert me_response.text == "<!doctype html><title>IM shell</title>"
