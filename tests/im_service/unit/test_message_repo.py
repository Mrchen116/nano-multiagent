"""Unit tests for message route registration and repository behavior."""

from pathlib import Path

from IM.app import create_app

from ._route_introspection import walk_routes


def test_create_app_registers_message_routes(tmp_path: Path) -> None:
    """Expose message create/list routes under conversation resources."""
    app = create_app(db_path=tmp_path / "im.db")
    route_paths = {
        route.path for route in walk_routes(app.routes) if hasattr(route, "path")
    }

    assert "/im/v1/conversations/{conversation_id}/messages" in route_paths
    assert "/im/ws/user" in route_paths
