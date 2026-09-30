"""Durable storage accounting, including in-flight upload reservations."""

import sqlite3

OWNER_LIMIT_BYTES = 1024**3
SERVICE_LIMIT_BYTES = 10 * 1024**3


def initialize_attachment_quota(connection: sqlite3.Connection) -> None:
    """Create the storage ledger without inventing ownership for historical files."""
    connection.execute(
        """CREATE TABLE IF NOT EXISTS attachment_storage (
            storage_name TEXT PRIMARY KEY,
            owner_id TEXT,
            byte_size INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL CHECK (state IN ('reserved', 'stored'))
        )"""
    )
    connection.execute(
        """INSERT OR IGNORE INTO attachment_storage
        (storage_name, owner_id, byte_size, state)
        SELECT storage_name, NULL, MAX(byte_size), 'stored'
        FROM message_images GROUP BY storage_name"""
    )
    connection.commit()
