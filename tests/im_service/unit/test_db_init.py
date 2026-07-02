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
    assert {"sender_type", "thinking_json", "elapsed_ms", "sender_display_name"} <= (
        message_columns
    )


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
