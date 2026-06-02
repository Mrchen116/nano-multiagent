"""SQLite connection and schema initialization helpers."""

from pathlib import Path
import json
import sqlite3

from IM.domain.models import managed_workspace_root

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    default_entry_node_id TEXT,
    password_hash TEXT,
    locale TEXT NOT NULL DEFAULT 'en',
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
    creator_id TEXT NOT NULL DEFAULT '',
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    unread_count INTEGER NOT NULL DEFAULT 0,
    last_message_preview TEXT,
    last_message_at TEXT,
    config_agent_id TEXT,
    config_profile_version INTEGER,
    config_system_prompt TEXT,
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
    tool_calls_json TEXT,
    token_usage_json TEXT,
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
    connection = sqlite3.connect(
        str(db_path), check_same_thread=False, cached_statements=0
    )
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
    _migrate_drop_nodes_capabilities_column(connection)
    _migrate_relay_tasks(connection)
    _migrate_usage_metrics(connection)
    _migrate_settings_policies(connection)
    _reconcile_conversation_summary_previews(connection)
    connection.commit()


def _migrate_users_owner_id(connection: sqlite3.Connection) -> None:
    """Backfill user ownership and default entry metadata for older schemas."""
    rows = connection.execute("PRAGMA table_info(users)").fetchall()
    column_names = {row["name"] for row in rows}
    if "owner_id" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN owner_id TEXT")
        connection.execute(
            "UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''"
        )
        connection.execute(
            "UPDATE users SET owner_id = id WHERE owner_id IS NULL OR owner_id = ''"
        )
    if "default_entry_node_id" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN default_entry_node_id TEXT")
    # feat-340-M1: multi-user auth — credentials and i18n locale per user.
    if "password_hash" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "locale" not in column_names:
        connection.execute(
            "ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'en'"
        )


def _migrate_conversations_metadata(connection: sqlite3.Connection) -> None:
    """Backfill conversation metadata columns introduced by IM-SPEC §6."""
    rows = connection.execute("PRAGMA table_info(conversations)").fetchall()
    column_names = {row["name"] for row in rows}
    if "type" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN type TEXT NOT NULL DEFAULT 'group'"
        )
    if "owner_id" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"
        )
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
    if "last_message_preview" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN last_message_preview TEXT"
        )
        connection.execute(
            """
            UPDATE conversations
            SET last_message_preview = (
                SELECT CASE
                    WHEN TRIM(COALESCE(messages.content, '')) <> '' THEN messages.content
                    ELSE ''
                END
                FROM messages
                WHERE messages.conversation_id = conversations.id
                ORDER BY messages.created_at DESC, messages.rowid DESC
                LIMIT 1
            )
            WHERE last_message_preview IS NULL
            """
        )
    if "config_agent_id" not in column_names:
        connection.execute("ALTER TABLE conversations ADD COLUMN config_agent_id TEXT")
    if "config_profile_version" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN config_profile_version INTEGER"
        )
    if "config_system_prompt" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN config_system_prompt TEXT"
        )
    # M234: creator_id records who created the conversation for dissolve-permission checks.
    # Legacy rows are backfilled with the first participant (owner_id fallback).
    if "creator_id" not in column_names:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN creator_id TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            """
            UPDATE conversations
            SET creator_id = COALESCE(
                (
                    SELECT user_id
                    FROM conversation_participants
                    WHERE conversation_id = conversations.id
                    ORDER BY rowid
                    LIMIT 1
                ),
                owner_id,
                ''
            )
            WHERE creator_id = ''
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
    # feat-340-M2: persist agent-runtime tool_calls / token_usage as nullable JSON columns.
    # Nullable because legacy user messages have neither; bridge writes populate them per-message.
    if "tool_calls_json" not in column_names:
        connection.execute("ALTER TABLE messages ADD COLUMN tool_calls_json TEXT")
    if "token_usage_json" not in column_names:
        connection.execute("ALTER TABLE messages ADD COLUMN token_usage_json TEXT")
    # feat-333-M2: embeds permission_request payload (pending/resolved) alongside tool_calls.
    if "permission_request_json" not in column_names:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN permission_request_json TEXT"
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
    if agent_rows and "workspace_root" in {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }:
        rows = connection.execute(
            "SELECT agent_id FROM agent_profiles WHERE workspace_root IS NULL OR TRIM(workspace_root) = ''"
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE agent_profiles SET workspace_root = ? WHERE agent_id = ?",
                (managed_workspace_root(str(row["agent_id"])), str(row["agent_id"])),
            )

    # bugfix-362: soft-stale columns for ghost-agent reconcile
    agent_column_names = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    if agent_column_names and "is_stale" not in agent_column_names:
        connection.execute(
            "ALTER TABLE agent_profiles ADD COLUMN is_stale INTEGER NOT NULL DEFAULT 0"
        )
    if agent_column_names and "staled_at" not in agent_column_names:
        connection.execute("ALTER TABLE agent_profiles ADD COLUMN staled_at TEXT")

    # feat-379-M2: per-agent feature flags and custom prompt supplement
    agent_column_names = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    if agent_column_names and "features_json" not in agent_column_names:
        connection.execute(
            "ALTER TABLE agent_profiles ADD COLUMN features_json TEXT NOT NULL DEFAULT '{}'"
        )
    if agent_column_names and "custom_prompt" not in agent_column_names:
        connection.execute("ALTER TABLE agent_profiles ADD COLUMN custom_prompt TEXT")

    # feat-394: heartbeat config persisted as JSON string per agent profile.
    agent_column_names = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    if agent_column_names and "heartbeat_json" not in agent_column_names:
        connection.execute("ALTER TABLE agent_profiles ADD COLUMN heartbeat_json TEXT")

    node_rows = connection.execute("PRAGMA table_info(nodes)").fetchall()
    node_column_names = {row["name"] for row in node_rows}
    if node_rows and "owner_id" not in node_column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN owner_id TEXT")


def _migrate_nodes_metadata(connection: sqlite3.Connection) -> None:
    """Backfill node config columns introduced by M99 node management APIs."""
    rows = connection.execute("PRAGMA table_info(nodes)").fetchall()
    column_names = {row["name"] for row in rows}
    if rows and "relay_enabled" not in column_names:
        connection.execute(
            "ALTER TABLE nodes ADD COLUMN relay_enabled INTEGER NOT NULL DEFAULT 1"
        )
    if rows and "reporting_enabled" not in column_names:
        connection.execute(
            "ALTER TABLE nodes ADD COLUMN reporting_enabled INTEGER NOT NULL DEFAULT 1"
        )
    if rows and "alias" not in column_names:
        connection.execute("ALTER TABLE nodes ADD COLUMN alias TEXT")


def _migrate_drop_nodes_capabilities_column(connection: sqlite3.Connection) -> None:
    """移除已废弃的 capabilities_json（能力改由网关按需解析，不再写入 IM）。"""
    rows = connection.execute("PRAGMA table_info(nodes)").fetchall()
    if not rows:
        return
    names = {str(row["name"]) for row in rows}
    if "capabilities_json" not in names:
        return
    try:
        connection.execute("ALTER TABLE nodes DROP COLUMN capabilities_json")
    except sqlite3.OperationalError:
        # SQLite < 3.35 不支持 DROP COLUMN；列可滞留，应用层已不再读写。
        pass


def _migrate_relay_tasks(connection: sqlite3.Connection) -> None:
    """Backfill relay task storage introduced by IM-SPEC §4."""
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
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
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
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


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _is_no_reply_protocol_token(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    return (
        normalized == "NO_REPLY"
        or normalized.startswith("suppressed_by=no_reply_token")
        or "suppressed_by=no_reply_token" in normalized
    )


def _preview_from_event(event_type: str, payload: dict[str, object]) -> str | None:
    content = _optional_text(payload.get("content"))
    if event_type in {"message.sent", "message_created"} and content is not None:
        return content
    if event_type in {
        "relay.processing",
        "relay.report",
        "relay.completed",
        "relay.failed",
        "message.delivered",
    }:
        summary = _optional_text(payload.get("summary"))
        detail = _optional_text(payload.get("detail"))
        preview = summary or detail or content
        if preview is None or _is_no_reply_protocol_token(preview):
            return None
        return preview
    file_name = _optional_text(payload.get("file_name"))
    if file_name is not None:
        return file_name
    attachments = payload.get("attachments")
    if isinstance(attachments, list) and attachments:
        return "Attachment"
    return None


def _preview_from_message_row(row: sqlite3.Row) -> str:
    content = str(row["content"] or "").strip()
    if content:
        return content
    try:
        attachments = json.loads(row["attachments_json"] or "[]")
    except json.JSONDecodeError:
        attachments = []
    if isinstance(attachments, list) and attachments:
        first = attachments[0] if isinstance(attachments[0], dict) else None
        if isinstance(first, dict):
            file_name = _optional_text(first.get("file_name"))
            if file_name is not None:
                return file_name
        return "Attachment"
    return ""


def _reconcile_conversation_summary_previews(connection: sqlite3.Connection) -> None:
    conversation_rows = connection.execute("SELECT id FROM conversations").fetchall()
    for conversation_row in conversation_rows:
        conversation_id = str(conversation_row["id"])
        latest_message = connection.execute(
            """
            SELECT content, attachments_json, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()
        latest_event = connection.execute(
            """
            SELECT event_type, payload_json, created_at
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY created_at DESC, event_id DESC
            """,
            (conversation_id,),
        ).fetchall()

        chosen_preview: str | None = None
        chosen_created_at: str | None = None
        if latest_message is not None:
            chosen_preview = _preview_from_message_row(latest_message)
            chosen_created_at = str(latest_message["created_at"])

        for event_row in latest_event:
            try:
                payload = json.loads(event_row["payload_json"])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event_preview = _preview_from_event(str(event_row["event_type"]), payload)
            if event_preview is None:
                continue
            event_created_at = str(event_row["created_at"])
            if chosen_created_at is None or event_created_at >= chosen_created_at:
                chosen_preview = event_preview
                chosen_created_at = event_created_at
            break

        if chosen_created_at is None:
            continue
        connection.execute(
            "UPDATE conversations SET last_message_preview = ?, last_message_at = ? WHERE id = ?",
            (chosen_preview, chosen_created_at, conversation_id),
        )


DEFAULT_SETTINGS_POLICIES = {
    "singleton_key": "default",
    "default_model": "codex_oauth:gpt-5.5",
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
