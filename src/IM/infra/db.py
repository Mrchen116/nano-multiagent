"""SQLite connection and schema initialization helpers."""

from pathlib import Path
import sqlite3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'group',
    owner_id TEXT NOT NULL DEFAULT '',
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    unread_count INTEGER NOT NULL DEFAULT 0,
    last_message_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, user_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    sender_user_id TEXT NOT NULL,
    sender_type TEXT NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    attachments_json TEXT NOT NULL DEFAULT '[]',
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    message_id TEXT,
    event_type TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relay_tasks (
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
    updated_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Create an SQLite connection for IM persistence.

    Args:
        db_path: Filesystem path of the SQLite database file.

    Returns:
        Open SQLite connection with row access by column name.

    Side Effects:
        Creates parent directories if missing and enables foreign key checks.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Initialize required IM tables in an idempotent way.

    Args:
        connection: SQLite connection that points to the target IM database.

    Side Effects:
        Executes DDL statements and commits the transaction.
    """
    connection.executescript(_SCHEMA_SQL)
    _migrate_users_owner_id(connection)
    _migrate_conversations_metadata(connection)
    _migrate_messages_metadata(connection)
    _migrate_relay_tasks(connection)
    connection.commit()


def _migrate_users_owner_id(connection: sqlite3.Connection) -> None:
    """Backfill owner_id for user rows created before the layered migration."""
    rows = connection.execute("PRAGMA table_info(users)").fetchall()
    column_names = {row["name"] for row in rows}
    if "owner_id" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN owner_id TEXT")
        connection.execute("UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''")
        connection.execute("UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''")


def _migrate_conversations_metadata(connection: sqlite3.Connection) -> None:
    """Backfill conversation metadata columns introduced by IM-SPEC §6."""
    rows = connection.execute("PRAGMA table_info(conversations)").fetchall()
    column_names = {row["name"] for row in rows}
    if "type" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN type TEXT NOT NULL DEFAULT 'group'"
        )
    if "owner_id" not in column_names:
        connection.execute("ALTER TABLE conversations ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
        connection.execute(
            """
            UPDATE conversations
            SET owner_id = COALESCE(
                (
                    SELECT users.owner_id
                    FROM conversation_participants
                    JOIN users ON users.id = conversation_participants.user_id
                    WHERE conversation_participants.conversation_id = conversations.id
                    ORDER BY conversation_participants.rowid
                    LIMIT 1
                ),
                ''
            )
            WHERE owner_id = ''
            """
        )
    if "is_pinned" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0"
        )
    if "is_muted" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN is_muted INTEGER NOT NULL DEFAULT 0"
        )
    if "unread_count" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN unread_count INTEGER NOT NULL DEFAULT 0"
        )
    if "last_message_at" not in column_names:
        connection.execute("ALTER TABLE conversations ADD COLUMN last_message_at TEXT")
        connection.execute(
            """
            UPDATE conversations
            SET last_message_at = (
                SELECT MAX(messages.created_at)
                FROM messages
                WHERE messages.conversation_id = conversations.id
            )
            WHERE last_message_at IS NULL
            """
        )


def _migrate_messages_metadata(connection: sqlite3.Connection) -> None:
    """Backfill message metadata columns introduced by IM-SPEC §6."""
    rows = connection.execute("PRAGMA table_info(messages)").fetchall()
    column_names = {row["name"] for row in rows}
    if "sender_type" not in column_names:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN sender_type TEXT NOT NULL DEFAULT 'user'"
        )
    if "attachments_json" not in column_names:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "delivery_status" not in column_names:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'completed'"
        )


def _migrate_relay_tasks(connection: sqlite3.Connection) -> None:
    """Backfill relay task storage introduced by IM-SPEC §4."""
    tables = {
        row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "relay_tasks" not in tables:
        connection.execute(
            """
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        return
    rows = connection.execute("PRAGMA table_info(relay_tasks)").fetchall()
    column_names = {row["name"] for row in rows}
    if "conversation_id" not in column_names:
        connection.execute("ALTER TABLE relay_tasks ADD COLUMN conversation_id TEXT")
        connection.execute(
            """
            UPDATE relay_tasks
            SET conversation_id = (
                SELECT conversation_id
                FROM messages
                WHERE messages.id = relay_tasks.message_id
            )
            WHERE conversation_id IS NULL OR conversation_id = ''
            """
        )
    if "receipt_status" not in column_names:
        connection.execute("ALTER TABLE relay_tasks ADD COLUMN receipt_status TEXT")
    if "receipt_detail" not in column_names:
        connection.execute("ALTER TABLE relay_tasks ADD COLUMN receipt_detail TEXT")
