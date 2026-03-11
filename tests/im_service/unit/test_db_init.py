"""Unit tests for IM SQLite schema bootstrap."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema


def test_initialize_schema_is_idempotent(tmp_path: Path) -> None:
    """Create all required IM tables and allow repeated initialization."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)

    initialize_schema(connection)
    initialize_schema(connection)

    table_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row[0] for row in table_rows}

    assert "users" in table_names
    assert "conversations" in table_names
    assert "conversation_participants" in table_names
    assert "messages" in table_names
    assert "conversation_events" in table_names
    assert "agent_profiles" in table_names
    assert "nodes" in table_names
    assert "bind_requests" in table_names
