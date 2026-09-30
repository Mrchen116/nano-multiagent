"""Durable company membership, sessions and bounded authentication counters."""

import sqlite3


def initialize_company_schema(connection: sqlite3.Connection) -> None:
    """Migrate existing humans to pending without granting implicit membership."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
    for name, definition in (
        ("membership_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("is_company_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("auth_epoch", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            epoch INTEGER NOT NULL,
            refresh_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS auth_sessions_user ON auth_sessions(user_id);
        CREATE TABLE IF NOT EXISTS auth_ws_tickets (
            ticket_hash TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES auth_sessions(session_id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_rate_limits (
            bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS auth_rate_expiry ON auth_rate_limits(expires_at);
        CREATE TABLE IF NOT EXISTS company_member_events (
            id INTEGER PRIMARY KEY,
            actor_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS company_initialization (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            admin_id TEXT NOT NULL,
            active_ids TEXT NOT NULL
        );
    """)
