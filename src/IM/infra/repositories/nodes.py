"""SQLite repositories for IM users, conversations, and messages."""

import sqlite3

from IM.domain.models import (
    NodeStatus,
)


from IM.infra._timestamps import utc_now


class NodeRepository:
    """Persist and query gateway node ownership, center config, and status."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_node(
        self,
        *,
        node_id: str,
        node_name: str,
        status: str = "offline",
        version: str = "",
        owner_id: str | None = None,
    ) -> NodeStatus:
        """Create or update a node row and return the stored snapshot."""
        normalized_status = _normalize_node_status(status=status, last_error=None)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO nodes(
                    node_id,
                    owner_id,
                    node_name,
                    status,
                    last_heartbeat_at,
                    agent_count,
                    version,
                    relay_enabled,
                    reporting_enabled,
                    alias,
                    last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = COALESCE(excluded.owner_id, nodes.owner_id),
                    node_name = excluded.node_name,
                    status = excluded.status,
                    version = excluded.version
                """,
                (
                    node_id,
                    owner_id,
                    node_name,
                    normalized_status,
                    "",
                    0,
                    version,
                    1,
                    1,
                    None,
                    None,
                ),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def record_gateway_registration(
        self,
        *,
        node_id: str,
        node_name: str,
        version: str,
        agent_count: int,
        owner_id: str | None = None,
    ) -> NodeStatus:
        """Persist node.register metadata as an online snapshot."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO nodes(
                    node_id,
                    owner_id,
                    node_name,
                    status,
                    last_heartbeat_at,
                    agent_count,
                    version,
                    relay_enabled,
                    reporting_enabled,
                    alias,
                    last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = COALESCE(excluded.owner_id, nodes.owner_id),
                    node_name = excluded.node_name,
                    status = excluded.status,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    agent_count = excluded.agent_count,
                    version = excluded.version,
                    last_error = excluded.last_error
                """,
                (
                    node_id,
                    owner_id,
                    node_name,
                    "online",
                    utc_now(),
                    max(agent_count, 0),
                    version,
                    1,
                    1,
                    None,
                    None,
                ),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def record_heartbeat(
        self,
        *,
        node_id: str,
        reported_status: str | None,
        agent_count: int | None,
        last_error: str | None,
        version: str | None,
    ) -> NodeStatus:
        """Persist node.heartbeat payload and derive canonical status aggregation."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            raise ValueError("node_id not found")
        next_status = _normalize_node_status(
            status=reported_status, last_error=last_error
        )
        next_agent_count = (
            existing.agent_count if agent_count is None else max(agent_count, 0)
        )
        next_version = existing.version if version is None else version
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET status = ?, last_heartbeat_at = ?, agent_count = ?, version = ?, last_error = ?
                WHERE node_id = ?
                """,
                (
                    next_status,
                    utc_now(),
                    next_agent_count,
                    next_version,
                    last_error,
                    node_id,
                ),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def list_nodes(self) -> list[NodeStatus]:
        """List node board snapshots in recency order."""
        rows = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes
            ORDER BY CASE status WHEN 'online' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                     COALESCE(last_heartbeat_at, '') DESC,
                     rowid DESC
            """
        ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def get_node(self, *, node_id: str) -> NodeStatus | None:
        """Return one node snapshot, or None when missing."""
        row = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def list_nodes_for_owner(self, *, owner_id: str) -> list[NodeStatus]:
        """Owner-scoped list — guarantees no cross-tenant leakage at the SQL layer."""
        rows = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes
            WHERE owner_id = ?
            ORDER BY CASE status WHEN 'online' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                     COALESCE(last_heartbeat_at, '') DESC,
                     rowid DESC
            """,
            (owner_id,),
        ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def get_node_for_owner(self, *, node_id: str, owner_id: str) -> NodeStatus | None:
        """Return the node only when its owner_id matches; else None."""
        node = self.get_node(node_id=node_id)
        if node is None or node.owner_id != owner_id:
            return None
        return node

    def assign_owner(self, *, node_id: str, owner_id: str) -> NodeStatus:
        """Bind a node to an owner and return the updated snapshot."""
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE nodes SET owner_id = ? WHERE node_id = ?",
                (owner_id, node_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("node_id not found")
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def update_node_config(
        self,
        *,
        node_id: str,
        alias: str | None,
        relay_enabled: bool | None,
        reporting_enabled: bool | None,
    ) -> NodeStatus:
        """Update node center config and return the latest snapshot."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            raise ValueError("node_id not found")
        next_alias = existing.alias if alias is None else (alias.strip() or None)
        next_relay_enabled = (
            existing.relay_enabled if relay_enabled is None else relay_enabled
        )
        next_reporting_enabled = (
            existing.reporting_enabled
            if reporting_enabled is None
            else reporting_enabled
        )
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET alias = ?, relay_enabled = ?, reporting_enabled = ?
                WHERE node_id = ?
                """,
                (
                    next_alias,
                    int(next_relay_enabled),
                    int(next_reporting_enabled),
                    node_id,
                ),
            )
        updated = self.get_node(node_id=node_id)
        assert updated is not None
        return updated

    def mark_disconnected(self, *, node_id: str) -> NodeStatus | None:
        """Mark a node offline when its websocket disconnects."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            return None
        with self._connection:
            self._connection.execute(
                "UPDATE nodes SET status = ? WHERE node_id = ?",
                ("offline", node_id),
            )
        return self.get_node(node_id=node_id)

    def _row_to_node(self, row: sqlite3.Row) -> NodeStatus:
        """Convert one row into a node status model."""
        return NodeStatus(
            node_id=row["node_id"],
            owner_id=row["owner_id"] or "",
            node_name=row["node_name"],
            status=row["status"],
            last_heartbeat_at=row["last_heartbeat_at"],
            agent_count=int(row["agent_count"]),
            version=row["version"],
            relay_enabled=bool(row["relay_enabled"]),
            reporting_enabled=bool(row["reporting_enabled"]),
            alias=row["alias"],
            last_error=row["last_error"],
        )


def _normalize_node_status(*, status: str | None, last_error: str | None) -> str:
    """Collapse raw gateway state into the canonical node board statuses."""
    normalized = (status or "").strip().lower()
    if last_error:
        return "degraded"
    if normalized in {"online", "offline", "degraded"}:
        return normalized
    if normalized in {"error", "failed", "warning", "degraded_partial"}:
        return "degraded"
    if normalized in {"connected", "healthy", "ready"}:
        return "online"
    if normalized in {"disconnected", "unknown", "timeout"}:
        return "offline"
    return "online" if normalized else "offline"
