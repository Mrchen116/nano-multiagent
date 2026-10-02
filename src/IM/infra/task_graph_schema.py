"""Migrate company task activity and receipts independently of chat lifetimes."""

import json
import sqlite3


def migrate_task_graph_company(connection: sqlite3.Connection) -> None:
    """Retain mutation receipts after graph deletion and seed known chat activity."""
    if connection.execute(
        "PRAGMA foreign_key_list(task_graph_mutation_receipts)"
    ).fetchall():
        connection.execute(
            "ALTER TABLE task_graph_mutation_receipts RENAME TO task_graph_receipts_old"
        )
        connection.execute("""CREATE TABLE task_graph_mutation_receipts (
            actor_key TEXT NOT NULL, request_key TEXT NOT NULL, operation_hash TEXT NOT NULL,
            graph_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(actor_key,request_key))""")
        connection.execute(
            "INSERT INTO task_graph_mutation_receipts SELECT * FROM task_graph_receipts_old"
        )
        connection.execute("DROP TABLE task_graph_receipts_old")
    connection.execute("""CREATE INDEX IF NOT EXISTS task_graph_delete_receipt_expiry
        ON task_graph_mutation_receipts(created_at)
        WHERE json_type(result_json,'$.deleted_ids')='array'""")
    connection.execute("""CREATE TABLE IF NOT EXISTS task_node_chat_activity (
        graph_id TEXT NOT NULL REFERENCES task_graphs(graph_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        updated_at TEXT NOT NULL, PRIMARY KEY(graph_id,node_id,conversation_id))""")
    for row in connection.execute("SELECT graph_id,document_json FROM task_graphs"):
        for node in json.loads(row["document_json"])["nodes"]:
            if node.get("last_chat_id"):
                connection.execute(
                    """INSERT OR IGNORE INTO task_node_chat_activity
                    SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM conversations WHERE id=?)""",
                    (
                        row["graph_id"],
                        node["id"],
                        node["last_chat_id"],
                        node["updated_at"],
                        node["last_chat_id"],
                    ),
                )
