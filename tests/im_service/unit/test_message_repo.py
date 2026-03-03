"""Unit tests for message route registration and repository behavior."""

from pathlib import Path

from IM.app import create_app


def test_create_app_registers_message_routes(tmp_path: Path) -> None:
    """Expose message create/list routes under conversation resources."""
    app = create_app(db_path=tmp_path / "im.db")
    route_paths = {route.path for route in app.routes}

    assert "/im/v1/conversations/{conversation_id}/messages" in route_paths
    assert "/im/v1/conversations/{conversation_id}/events" in route_paths
