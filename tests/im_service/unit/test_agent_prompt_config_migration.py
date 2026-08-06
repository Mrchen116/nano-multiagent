"""Behavior tests for the public Agent prompt schema cutover."""

from pathlib import Path

import pytest

from IM.infra import db
from IM.infra.db import connect, initialize_schema


@pytest.mark.parametrize(
    ("legacy", "custom", "expected"),
    [
        ("   ", "Keep custom", "Keep custom"),
        ("Legacy role", None, "Legacy role"),
        (" Same role ", "Same role", "Same role"),
        ("Legacy role", "Custom tail", "Legacy role\n\nCustom tail"),
    ],
)
def test_initialize_schema_migrates_legacy_agent_prompt_once(
    tmp_path: Path,
    legacy: str,
    custom: str | None,
    expected: str,
) -> None:
    """Upgrade legacy prompt pairs using the prior runtime order, idempotently."""
    connection = connect(tmp_path / "legacy-agent-prompt.db")
    initialize_schema(connection)
    agent_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    if "system_prompt" not in agent_columns:
        connection.execute(
            "ALTER TABLE agent_profiles ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        """
        INSERT INTO agent_profiles(
            agent_id, owner_id, display_name, description, skills_json,
            tool_allowlist_json, group_reply_policy, profile_version,
            created_at, updated_at, custom_prompt, system_prompt
        ) VALUES ('agent-a', 'owner-a', 'Agent A', '', '[]', '[]', 'MENTION', 1,
                  '2026-08-06T00:00:00Z', '2026-08-06T00:00:00Z', ?, ?)
        """,
        (custom, legacy),
    )
    connection.commit()

    initialize_schema(connection)
    initialize_schema(connection)

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    row = connection.execute(
        "SELECT custom_prompt FROM agent_profiles WHERE agent_id = 'agent-a'"
    ).fetchone()
    assert "system_prompt" not in columns
    assert row["custom_prompt"] == expected


def test_initialize_schema_removes_conversation_prompt_copy_without_losing_chat(
    tmp_path: Path,
) -> None:
    """Drop legacy prompt provenance while preserving conversation identity/version."""
    connection = connect(tmp_path / "legacy-conversation-prompt.db")
    initialize_schema(connection)
    conversation_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "config_system_prompt" not in conversation_columns:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN config_system_prompt TEXT"
        )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, config_agent_id,
            config_profile_version, config_system_prompt, created_at
        ) VALUES ('conversation-a', 'Existing chat', 'direct', 'owner-a', 'owner-a',
                  'agent-a', 7, 'Hidden role', '2026-08-06T00:00:00Z')
        """
    )
    connection.commit()

    initialize_schema(connection)

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
    }
    row = connection.execute(
        """
        SELECT id, config_agent_id, config_profile_version
        FROM conversations WHERE id = 'conversation-a'
        """
    ).fetchone()
    assert "config_system_prompt" not in columns
    assert tuple(row) == ("conversation-a", "agent-a", 7)


def test_initialize_schema_clears_legacy_prompt_data_when_sqlite_cannot_drop_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep legacy storage inert and migration idempotent on SQLite before 3.35."""
    connection = db.connect(tmp_path / "legacy-agent-prompt-old-sqlite.db")
    db.initialize_schema(connection)
    connection.execute(
        "ALTER TABLE agent_profiles ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''"
    )
    connection.execute("ALTER TABLE conversations ADD COLUMN config_system_prompt TEXT")
    connection.execute(
        """
        INSERT INTO agent_profiles(
            agent_id, owner_id, display_name, description, skills_json,
            tool_allowlist_json, group_reply_policy, profile_version,
            created_at, updated_at, custom_prompt, system_prompt
        ) VALUES ('agent-a', 'owner-a', 'Agent A', '', '[]', '[]', 'MENTION', 1,
                  '2026-08-06T00:00:00Z', '2026-08-06T00:00:00Z',
                  'Custom tail', 'Legacy role')
        """
    )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, config_agent_id,
            config_profile_version, config_system_prompt, created_at
        ) VALUES ('conversation-a', 'Existing chat', 'direct', 'owner-a', 'owner-a',
                  'agent-a', 7, 'Hidden role', '2026-08-06T00:00:00Z')
        """
    )
    connection.commit()
    monkeypatch.setattr(db.sqlite3, "sqlite_version_info", (3, 34, 0))

    db.initialize_schema(connection)
    db.initialize_schema(connection)

    agent_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(agent_profiles)")
    }
    conversation_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(conversations)")
    }
    agent = connection.execute(
        "SELECT custom_prompt, system_prompt FROM agent_profiles WHERE agent_id = 'agent-a'"
    ).fetchone()
    conversation = connection.execute(
        "SELECT config_system_prompt FROM conversations WHERE id = 'conversation-a'"
    ).fetchone()

    assert "system_prompt" in agent_columns
    assert "config_system_prompt" in conversation_columns
    assert tuple(agent) == ("Legacy role\n\nCustom tail", "")
    assert conversation["config_system_prompt"] == ""
