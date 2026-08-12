"""Unit tests for SQLite schema migration and backfill logic."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema


def test_initialize_schema_adds_nullable_reasoning_effort_to_legacy_profiles(
    tmp_path: Path,
) -> None:
    """Upgrade existing profile rows without inventing a reasoning selection."""
    connection = connect(tmp_path / "legacy.db")
    connection.execute(
        """
        CREATE TABLE agent_profiles (
            agent_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            node_id TEXT,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            skills_json TEXT NOT NULL DEFAULT '[]',
            tool_allowlist_json TEXT NOT NULL DEFAULT '[]',
            group_reply_policy TEXT NOT NULL DEFAULT 'manual',
            default_model TEXT,
            workspace_root TEXT,
            profile_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO agent_profiles(
            agent_id, owner_id, display_name, default_model, workspace_root,
            created_at, updated_at
        ) VALUES ('legacy', 'owner', 'Legacy', 'model-a', '/srv/legacy', 't0', 't0')
        """
    )
    connection.commit()

    initialize_schema(connection)

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(agent_profiles)")
    }
    row = connection.execute(
        "SELECT reasoning_effort FROM agent_profiles WHERE agent_id = 'legacy'"
    ).fetchone()
    assert "reasoning_effort" in columns
    assert row["reasoning_effort"] is None


def test_initialize_schema_preserves_missing_agent_workspace_roots(
    tmp_path: Path,
) -> None:
    """Legacy NULL roots remain unknown until their Gateway declares one."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO agent_profiles(
            agent_id,
            owner_id,
            node_id,
            display_name,
            description,
            custom_prompt,
            skills_json,
            tool_allowlist_json,
            group_reply_policy,
            default_model,
            workspace_root,
            profile_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "agent-legacy",
            "",
            None,
            "Legacy",
            "legacy row",
            "You are Legacy.",
            "[]",
            "[]",
            "manual",
            None,
            None,
            1,
            "2026-03-17T00:00:00Z",
            "2026-03-17T00:00:00Z",
        ),
    )
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT workspace_root, workspace_is_default FROM agent_profiles WHERE agent_id = ?",
        ("agent-legacy",),
    ).fetchone()
    assert row is not None
    assert row["workspace_root"] is None
    assert row["workspace_is_default"] is None


def test_initialize_schema_backfills_last_message_preview_from_latest_message(
    tmp_path: Path,
) -> None:
    """Backfill last_message_preview so inbox list data survives restarts without N message fetches."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("user-1", "alice", "Alice", "owner-1", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "conv-1",
            "Alpha",
            "direct",
            "owner-1",
            "user-1",
            0,
            0,
            1,
            "2026-03-26T00:02:00Z",
            "2026-03-26T00:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO conversation_participants(conversation_id, user_id)
        VALUES (?, ?)
        """,
        ("conv-1", "user-1"),
    )
    connection.execute(
        """
        INSERT INTO messages(
            id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "msg-1",
            "conv-1",
            "user-1",
            "user",
            "latest preview",
            "[]",
            "completed",
            "2026-03-26T00:02:00Z",
        ),
    )
    connection.commit()

    connection.execute("ALTER TABLE conversations DROP COLUMN last_message_preview")
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT last_message_preview FROM conversations WHERE id = ?",
        ("conv-1",),
    ).fetchone()
    assert row is not None
    assert row["last_message_preview"] == "latest preview"


def test_initialize_schema_reconciles_old_relay_preview_mismatches(
    tmp_path: Path,
) -> None:
    """Recompute stale conversation previews from the latest visible relay event on startup."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("user-1", "alice", "Alice", "owner-1", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "conv-1",
            "Alpha",
            "direct",
            "owner-1",
            "user-1",
            0,
            0,
            1,
            "11",
            "2026-03-26T00:01:00Z",
            "2026-03-26T00:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO conversation_participants(conversation_id, user_id)
        VALUES (?, ?)
        """,
        ("conv-1", "user-1"),
    )
    connection.execute(
        """
        INSERT INTO messages(
            id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "msg-1",
            "conv-1",
            "user-1",
            "user",
            "11",
            "[]",
            "completed",
            "2026-03-26T00:01:00Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO conversation_events(
            conversation_id, message_id, event_type, delivery_status, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "conv-1",
            "msg-1",
            "relay.completed",
            "completed",
            '{"message_id":"msg-1","relay_task_id":"relay-1","detail":"A\\n\\nGot it. What would you like to do?"}',
            "2026-03-26T00:02:00Z",
        ),
    )
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT last_message_preview, last_message_at FROM conversations WHERE id = ?",
        ("conv-1",),
    ).fetchone()
    assert row is not None
    assert row["last_message_preview"] == "A\n\nGot it. What would you like to do?"
    assert row["last_message_at"] == "2026-03-26T00:02:00Z"
