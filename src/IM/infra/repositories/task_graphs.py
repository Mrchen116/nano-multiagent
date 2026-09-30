"""Store task documents and mutation receipts in the caller's SQLite transaction."""

from __future__ import annotations

import json
import sqlite3


class TaskGraphRepository:
    """Keep graph JSON and idempotency receipts under one transaction owner."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def actor_user(
        self, kind: str, actor_id: str, node_id: str | None
    ) -> sqlite3.Row | None:
        """Resolve a real user or a node-owned, currently registered PA Agent."""
        if kind == "user":
            return self.db.execute(
                "SELECT id, owner_id, display_name FROM users WHERE id=? AND membership_status='active'",
                (actor_id,),
            ).fetchone()
        # The synthetic chat user has its own identity; human ownership is
        # authoritative on the registered Agent profile, not that users row.
        return self.db.execute(
            """SELECT u.id, p.owner_id, p.display_name FROM agent_profiles p
            JOIN users u ON u.username='agent:' || p.agent_id
            JOIN nodes n ON n.node_id=p.node_id AND n.owner_id=p.owner_id
            JOIN users owner ON owner.owner_id=p.owner_id AND owner.username NOT LIKE 'agent:%'
            WHERE p.agent_id=? AND p.node_id=? AND p.is_stale=0
            AND owner.membership_status='active' AND n.status='online'
            AND COALESCE(json_extract(p.features_json,'$.task_graph'),1)=1
            AND EXISTS(SELECT 1 FROM json_each(p.tool_allowlist_json) WHERE value='task_graph')""",
            (actor_id, node_id),
        ).fetchone()

    def member_conversation(
        self, conversation_id: str, user_id: str
    ) -> sqlite3.Row | None:
        """Read a conversation only when the current principal is a participant."""
        return self.db.execute(
            """SELECT c.id,c.title FROM conversations c
            JOIN conversation_participants p ON p.conversation_id=c.id
            WHERE c.id=? AND p.user_id=?""",
            (conversation_id, user_id),
        ).fetchone()

    def get(self, graph_id: str) -> dict | None:
        """Read the authoritative document, or None if it no longer exists."""
        row = self.db.execute(
            "SELECT owner_id, document_json FROM task_graphs WHERE graph_id=?",
            (graph_id,),
        ).fetchone()
        return (
            {**json.loads(row["document_json"]), "owner_id": row["owner_id"]}
            if row is not None
            else None
        )

    def receipt(self, actor_key: str, request_key: str) -> sqlite3.Row | None:
        """Read a prior write result after the service has checked current access."""
        return self.db.execute(
            "SELECT operation_hash,result_json FROM task_graph_mutation_receipts WHERE actor_key=? AND request_key=?",
            (actor_key, request_key),
        ).fetchone()

    def save(
        self,
        document: dict,
        *,
        actor_key: str,
        request_key: str,
        operation_hash: str,
        result: dict,
    ) -> None:
        """Write the document, summary and replay result without committing early."""
        root = next(n for n in document["nodes"] if n["id"] == document["root_node_id"])
        self.db.execute(
            """INSERT INTO task_graphs
            (graph_id,owner_id,root_title,revision,document_json,created_at,updated_at,updated_by)
            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET
            root_title=excluded.root_title,revision=excluded.revision,document_json=excluded.document_json,
            updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (
                document["graph_id"],
                document["owner_id"],
                root["title"],
                document["revision"],
                json.dumps(
                    {k: v for k, v in document.items() if k != "owner_id"},
                    ensure_ascii=False,
                ),
                document["created_at"],
                document["updated_at"],
                document["updated_by"],
            ),
        )
        self.db.execute(
            """INSERT INTO task_graph_mutation_receipts
            (actor_key,request_key,operation_hash,graph_id,result_json,created_at) VALUES (?,?,?,?,?,?)""",
            (
                actor_key,
                request_key,
                operation_hash,
                document["graph_id"],
                json.dumps(result, ensure_ascii=False),
                document["updated_at"],
            ),
        )

    def list_for_owner(
        self,
        *,
        owner_id: str,
        query: str,
        after: tuple[str, str] | None,
        limit: int,
    ) -> tuple[list[sqlite3.Row], int]:
        """Page company summaries in most-recently-updated order."""
        clause = "FROM task_graphs WHERE 1=1"
        args: list = []
        if query:
            clause += " AND INSTR(LOWER(root_title),LOWER(?))>0"
            args.append(query)
        total = self.db.execute("SELECT COUNT(*) " + clause, args).fetchone()[0]
        if after:
            clause += " AND (updated_at,graph_id)<(?,?)"
            args.extend(after)
        rows = self.db.execute(
            "SELECT document_json "
            + clause
            + " ORDER BY updated_at DESC,graph_id DESC LIMIT ?",
            [*args, limit + 1],
        ).fetchall()
        return rows, total

    def record_activity(
        self, document: dict, changed: list[str], conversation_id: str | None
    ) -> None:
        """Keep every verified chat association for each surviving changed node."""
        if conversation_id:
            self.db.executemany(
                """INSERT INTO task_node_chat_activity VALUES (?,?,?,?)
                ON CONFLICT(graph_id,node_id,conversation_id) DO UPDATE SET updated_at=excluded.updated_at""",
                [
                    (
                        document["graph_id"],
                        node_id,
                        conversation_id,
                        document["updated_at"],
                    )
                    for node_id in changed
                ],
            )

    def activity(self, conversation_id: str) -> list[dict]:
        """Project current node summaries for one already-authorized chat."""
        result = []
        for row in self.db.execute(
            """SELECT a.node_id,a.updated_at,g.document_json FROM task_node_chat_activity a
                JOIN task_graphs g ON g.graph_id=a.graph_id WHERE a.conversation_id=? ORDER BY a.updated_at DESC""",
            (conversation_id,),
        ):
            graph = json.loads(row["document_json"])
            nodes = {n["id"]: n for n in graph["nodes"]}
            node = nodes.get(row["node_id"])
            if node:
                result.append(
                    dict(
                        graph_id=graph["graph_id"],
                        node_id=node["id"],
                        scope_id=node["container_id"],
                        title=node["title"],
                        root_title=nodes[graph["root_node_id"]]["title"],
                        status=node["status"],
                        updated_at=row["updated_at"],
                    )
                )
        return result

    def source_message(self, message_id: str, user_id: str) -> sqlite3.Row | None:
        """Resolve a human source only inside the executing Agent's actual chat ACL."""
        return self.db.execute(
            """SELECT m.*,c.external_source FROM messages m
            JOIN conversations c ON c.id=m.conversation_id
            JOIN conversation_participants p ON p.conversation_id=c.id AND p.user_id=?
            WHERE m.id=? AND m.sender_type='user'""",
            (user_id, message_id),
        ).fetchone()

    def delete(self, document: dict, removed: list[str], **receipt: object) -> None:
        """Commit a subtree or graph removal while retaining its replay receipt."""
        if document["nodes"]:
            self.save(document, **receipt)
            self.db.executemany(
                "DELETE FROM task_node_chat_activity WHERE graph_id=? AND node_id=?",
                [(document["graph_id"], node) for node in removed],
            )
        else:
            self.db.execute(
                "DELETE FROM task_graphs WHERE graph_id=?", (document["graph_id"],)
            )
            self.db.execute(
                """INSERT INTO task_graph_mutation_receipts VALUES (?,?,?,?,?,?)""",
                (
                    receipt["actor_key"],
                    receipt["request_key"],
                    receipt["operation_hash"],
                    document["graph_id"],
                    json.dumps(receipt["result"]),
                    document["updated_at"],
                ),
            )
