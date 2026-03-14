"""SQLite connection and schema initialization helpers."""

from pathlib import Path
import sqlite3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    default_entry_node_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings_policies (
    singleton_key TEXT PRIMARY KEY,
    default_model TEXT NOT NULL,
    max_turn_per_run INTEGER NOT NULL,
    max_attachment_size_mb INTEGER NOT NULL,
    retention_days INTEGER NOT NULL,
    audit_level TEXT NOT NULL,
    rate_limit_per_min INTEGER NOT NULL
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
    config_profile_version INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    node_id TEXT,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL,
    skills_json TEXT NOT NULL DEFAULT '[]',
    tool_allowlist_json TEXT NOT NULL DEFAULT '[]',
    group_reply_policy TEXT NOT NULL DEFAULT 'manual',
    default_model TEXT,
    workspace_root TEXT,
    profile_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    owner_id TEXT,
    node_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline',
    last_heartbeat_at TEXT NOT NULL DEFAULT '',
    agent_count INTEGER NOT NULL DEFAULT 0,
    version TEXT NOT NULL DEFAULT '',
    relay_enabled INTEGER NOT NULL DEFAULT 1,
    reporting_enabled INTEGER NOT NULL DEFAULT 1,
    alias TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS usage_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT,
    conversation_id TEXT,
    agent_id TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    turns INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bind_requests (
    bind_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL,
    bind_token TEXT NOT NULL UNIQUE,
    bind_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT
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

    Notes:
        FastAPI serves some IM reads in worker threads while sharing one app-scoped
        connection. Disable sqlite3's per-connection statement cache so concurrent
        parameter binding cannot leak across threads and trigger InterfaceError or
        stale row reads on the shared handle.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), check_same_thread=False, cached_statements=0)
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
    _migrate_agent_profile_tables(connection)
    _migrate_nodes_metadata(connection)
    _migrate_relay_tasks(connection)
    _migrate_usage_metrics(connection)
    _migrate_settings_policies(connection)
    connection.commit()


def _migrate_users_owner_id(connection: sqlite3.Connection) -> None:
    """Backfill user ownership and default entry metadata for older schemas."""
    rows = connection.execute("PRAGMA table_info(users)").fetchall()
    column_names = {row["name"] for row in rows}
    if "owner_id" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN owner_id TEXT")
        connection.execute("UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''")
        connection.execute("UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''")
    if "default_entry_node_id" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN default_entry_node_id TEXT")




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
    if "config_profile_version" not in column_names:
        connection.execute("ALTER TABLE conversations ADD COLUMN config_profile_version INTEGER")


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


def _migrate_agent_profile_tables(connection: sqlite3.Connection) -> None:
    """Backfill newer IM tables and columns needed by M96 APIs."""
    agent_rows = connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    agent_column_names = {row["name"] for row in agent_rows}
    if agent_rows and "description" not in agent_column_names:
        connection.execute(
            "ALTER TABLE agent_profiles ADD COLUMN description TEXT NOT NULL DEFAULT ''"
        )
    if agent_rows and "workspace_root" not in agent_column_names:
        connection.execute("ALTER TABLE agent_profiles ADD COLUMN workspace_root TEXT")

    node_rows = connection.execute("PRAGMA table_info(nodes)").fetchall()
    node_column_names = {row["name"] for row in node_rows}
    if node_rows and "owner_id" not in node_column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN owner_id TEXT")


def _migrate_nodes_metadata(connection: sqlite3.Connection) -> None:
    """Backfill node config columns introduced by M99 node management APIs."""
    rows = connection.execute("PRAGMA table_info(nodes)").fetchall()
    column_names = {row["name"] for row in rows}
    if rows and "relay_enabled" not in column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN relay_enabled INTEGER NOT NULL DEFAULT 1")
    if rows and "reporting_enabled" not in column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN reporting_enabled INTEGER NOT NULL DEFAULT 1")
    if rows and "alias" not in column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN alias TEXT")


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


def _migrate_usage_metrics(connection: sqlite3.Connection) -> None:
    """Create usage metrics table for M99 token/turn aggregation when missing."""
    tables = {
        row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "usage_metrics" in tables:
        return
    connection.execute(
        """
        CREATE TABLE usage_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT,
            conversation_id TEXT,
            agent_id TEXT,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            turns INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )


DEFAULT_SETTINGS_POLICIES = {
    "singleton_key": "default",
    "default_model": "gpt-5.2-codex",
    "max_turn_per_run": 14,
    "max_attachment_size_mb": 15,
    "retention_days": 30,
    "audit_level": "basic",
    "rate_limit_per_min": 45,
}


def _migrate_settings_policies(connection: sqlite3.Connection) -> None:
    """Ensure the singleton settings-policy row exists for settings center APIs."""
    connection.execute(
        """
        INSERT INTO settings_policies(
            singleton_key,
            default_model,
            max_turn_per_run,
            max_attachment_size_mb,
            retention_days,
            audit_level,
            rate_limit_per_min
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(singleton_key) DO NOTHING
        """,
        (
            DEFAULT_SETTINGS_POLICIES["singleton_key"],
            DEFAULT_SETTINGS_POLICIES["default_model"],
            DEFAULT_SETTINGS_POLICIES["max_turn_per_run"],
            DEFAULT_SETTINGS_POLICIES["max_attachment_size_mb"],
            DEFAULT_SETTINGS_POLICIES["retention_days"],
            DEFAULT_SETTINGS_POLICIES["audit_level"],
            DEFAULT_SETTINGS_POLICIES["rate_limit_per_min"],
        ),
    )
