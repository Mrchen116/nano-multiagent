"""Unit tests for IM SQLite schema bootstrap."""

from pathlib import Path
import threading

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
    assert "agent_config_boundaries" in table_names

    conversation_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
    }
    message_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(messages)").fetchall()
    }
    conversation_indexes = {
        row["name"]
        for row in connection.execute("PRAGMA index_list(conversations)").fetchall()
    }

    assert {"external_source", "external_chat_id"} <= conversation_columns
    assert "sender_display_name" in message_columns
    assert "idx_conversations_external_identity" in conversation_indexes
    assert "idx_conversations_external_identity_unique" in conversation_indexes
    boundary_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(agent_config_boundaries)"
        ).fetchall()
    }
    assert {
        "boundary_id",
        "conversation_id",
        "before_message_id",
        "runtime_fingerprint",
        "event_id",
    } <= boundary_columns


def test_initialize_schema_migrates_boundary_profile_provenance_to_nullable(
    tmp_path: Path,
) -> None:
    """An IM restart upgrades existing boundary rows without losing provenance."""
    connection = connect(tmp_path / "legacy-boundary.db")
    initialize_schema(connection)
    connection.executescript(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES ('owner-1', 'owner', 'Owner', 'owner-1', '2026-07-22T00:00:00Z');
        INSERT INTO conversations(id, title, owner_id, creator_id, created_at)
        VALUES ('conversation-1', 'Chat', 'owner-1', 'owner-1', '2026-07-22T00:00:00Z');
        INSERT INTO messages(
            id, conversation_id, sender_user_id, content, delivery_status, created_at
        ) VALUES (
            'message-1', 'conversation-1', 'owner-1', 'anchor', 'completed',
            '2026-07-22T00:00:00Z'
        );
        INSERT INTO conversation_events(
            event_id, conversation_id, event_type, delivery_status, payload_json, created_at
        ) VALUES (
            1, 'conversation-1', 'agent.config.changed', 'completed', '{}',
            '2026-07-22T00:00:00Z'
        );
        """
    )
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.executescript(
        """
        DROP TABLE agent_config_boundaries;
        CREATE TABLE agent_config_boundaries (
            boundary_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            before_message_id TEXT NOT NULL,
            runtime_fingerprint TEXT NOT NULL,
            fingerprint_schema TEXT NOT NULL,
            profile_version INTEGER NOT NULL,
            applied_at TEXT NOT NULL,
            event_id INTEGER NOT NULL UNIQUE,
            UNIQUE(conversation_id, before_message_id, runtime_fingerprint),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (before_message_id) REFERENCES messages(id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES conversation_events(event_id) ON DELETE CASCADE
        );
        INSERT INTO agent_config_boundaries(
            boundary_id, conversation_id, agent_id, before_message_id,
            runtime_fingerprint, fingerprint_schema, profile_version, applied_at, event_id
        ) VALUES ('boundary-1', 'conversation-1', 'agent-1', 'message-1',
                  'fingerprint-1', 'v1', 7, '2026-07-22T00:00:00Z', 1);
        """
    )
    connection.execute("PRAGMA foreign_keys = ON")

    initialize_schema(connection)

    profile_version = next(
        row
        for row in connection.execute(
            "PRAGMA table_info(agent_config_boundaries)"
        ).fetchall()
        if row["name"] == "profile_version"
    )
    row = connection.execute(
        "SELECT profile_version FROM agent_config_boundaries WHERE boundary_id = 'boundary-1'"
    ).fetchone()
    assert profile_version["notnull"] == 0
    assert row["profile_version"] == 7


def test_initialize_schema_owns_dispatch_log_without_changing_legacy_rows(
    tmp_path: Path,
) -> None:
    """Schema bootstrap preserves the handler-era dispatch table shape and data."""
    connection = connect(tmp_path / "legacy-dispatch.db")
    connection.execute(
        """
        CREATE TABLE agent_message_dispatch_log (
            dispatch_request_key TEXT PRIMARY KEY,
            source_agent_id TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            target_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO agent_message_dispatch_log(
            dispatch_request_key, source_agent_id, target_kind, target_id,
            conversation_id, message_id, created_at
        ) VALUES ('A:call-1', 'A', 'agent_id', 'B', 'conv-1', 'msg-1', '2026-01-01T00:00:00Z')
        """
    )
    connection.commit()

    initialize_schema(connection)

    columns = [
        (row["name"], row["type"], row["notnull"], row["pk"])
        for row in connection.execute(
            "PRAGMA table_info(agent_message_dispatch_log)"
        ).fetchall()
    ]
    row = connection.execute(
        "SELECT * FROM agent_message_dispatch_log WHERE dispatch_request_key = 'A:call-1'"
    ).fetchone()
    assert columns == [
        ("dispatch_request_key", "TEXT", 0, 1),
        ("source_agent_id", "TEXT", 1, 0),
        ("target_kind", "TEXT", 1, 0),
        ("target_id", "TEXT", 1, 0),
        ("conversation_id", "TEXT", 1, 0),
        ("message_id", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ]
    assert tuple(row) == (
        "A:call-1",
        "A",
        "agent_id",
        "B",
        "conv-1",
        "msg-1",
        "2026-01-01T00:00:00Z",
    )


def test_initialize_schema_migrates_legacy_conversations_before_external_index(
    tmp_path: Path,
) -> None:
    """Older IM DBs without external columns should start and gain the M7 index."""
    connection = connect(tmp_path / "legacy-im.db")
    connection.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conversation_participants (
            conversation_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (conversation_id, user_id)
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender_user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments_json TEXT NOT NULL DEFAULT '[]',
            delivery_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    connection.commit()

    initialize_schema(connection)

    conversation_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
    }
    conversation_indexes = {
        row["name"]
        for row in connection.execute("PRAGMA index_list(conversations)").fetchall()
    }
    message_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(messages)").fetchall()
    }

    assert {"external_source", "external_chat_id", "config_agent_id", "owner_id"} <= (
        conversation_columns
    )
    assert "idx_conversations_external_identity" in conversation_indexes
    assert "idx_conversations_external_identity_unique" in conversation_indexes
    assert {"sender_type", "thinking_json", "elapsed_ms", "sender_display_name"} <= (
        message_columns
    )


def test_initialize_schema_deduplicates_legacy_external_conversations(
    tmp_path: Path,
) -> None:
    """Legacy duplicate shadow rows are merged before the unique index is added."""
    connection = connect(tmp_path / "legacy-duplicates.db")
    connection.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'group',
            owner_id TEXT NOT NULL DEFAULT '',
            config_agent_id TEXT,
            external_source TEXT,
            external_chat_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conversation_participants (
            conversation_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (conversation_id, user_id)
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender_user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments_json TEXT NOT NULL DEFAULT '[]',
            delivery_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conversation_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            message_id TEXT,
            event_type TEXT NOT NULL,
            delivery_status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE relay_tasks (
            relay_task_id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            receipt_status TEXT,
            receipt_detail TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES ('owner', 'owner', 'Owner', 'owner', '2026-01-01T00:00:00Z');
        INSERT INTO conversations(
            id, title, type, owner_id, config_agent_id,
            external_source, external_chat_id, created_at
        )
        VALUES
          ('conv-a', 'A', 'direct', 'owner', 'plato', 'feishu', 'oc_1', '2026-01-01T00:00:00Z'),
          ('conv-b', 'B', 'direct', 'owner', 'plato', 'feishu', 'oc_1', '2026-01-01T00:00:01Z');
        INSERT INTO conversation_participants(conversation_id, user_id)
        VALUES ('conv-a', 'owner'), ('conv-b', 'owner');
        INSERT INTO messages(
            id, conversation_id, sender_user_id, content,
            attachments_json, delivery_status, created_at
        )
        VALUES
          ('msg-a', 'conv-a', 'owner', 'a', '[]', 'completed', '2026-01-01T00:00:02Z'),
          ('msg-b', 'conv-b', 'owner', 'b', '[]', 'completed', '2026-01-01T00:00:03Z');
        """
    )
    connection.commit()

    initialize_schema(connection)

    conversations = connection.execute(
        """
        SELECT id
        FROM conversations
        WHERE external_source = 'feishu'
          AND external_chat_id = 'oc_1'
          AND config_agent_id = 'plato'
          AND owner_id = 'owner'
        """
    ).fetchall()
    message_conversation_ids = {
        row["conversation_id"]
        for row in connection.execute(
            "SELECT conversation_id FROM messages ORDER BY id"
        ).fetchall()
    }

    assert [row["id"] for row in conversations] == ["conv-a"]
    assert message_conversation_ids == {"conv-a"}


def test_connect_supports_cross_thread_parameterized_reads_without_interface_errors(
    tmp_path: Path,
) -> None:
    """Keep shared cross-thread reads stable for FastAPI threadpool handlers."""
    connection = connect(tmp_path / "im.db")
    connection.execute(
        "CREATE TABLE read_probe (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )
    for index in range(64):
        connection.execute(
            "INSERT INTO read_probe(id, payload) VALUES (?, ?)",
            (f"row-{index}", f"payload-{index}"),
        )
    connection.commit()

    barrier = threading.Barrier(8)
    failures: list[BaseException] = []

    def _reader(reader_index: int) -> None:
        try:
            barrier.wait(timeout=2.0)
            for iteration in range(2000):
                row_id = f"row-{(reader_index + iteration) % 64}"
                row = connection.execute(
                    "SELECT payload FROM read_probe WHERE id = ?",
                    (row_id,),
                ).fetchone()
                assert row is not None
                assert row[0] == f"payload-{(reader_index + iteration) % 64}"
        except BaseException as exc:  # noqa: BLE001
            failures.append(exc)

    threads = [threading.Thread(target=_reader, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
