"""Unit tests for IM FastAPI application factory."""

from pathlib import Path

from IM.app import create_app


def test_create_app_registers_im_routes(tmp_path: Path) -> None:
    """Build IM app with required base routes for users and conversations."""
    app = create_app(db_path=tmp_path / "im.db")
    route_paths = {route.path for route in app.routes}

    assert "/im/v1/users" in route_paths
    assert "/im/v1/conversations" in route_paths
