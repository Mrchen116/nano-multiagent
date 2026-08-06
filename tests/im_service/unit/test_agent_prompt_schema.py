"""Schema coverage for the sole visible Agent prompt field."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema


def test_fresh_schema_has_custom_prompt_without_retired_prompt_columns(
    tmp_path: Path,
) -> None:
    """Fresh IM storage only creates the visible Agent prompt column."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    profile_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    conversation_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
    }

    assert "custom_prompt" in profile_columns
    assert "system_prompt" not in profile_columns
    assert "config_system_prompt" not in conversation_columns
