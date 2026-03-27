"""Application service for IM node board and node config APIs."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from IM.domain.models import NodeStatus
from IM.infra.repositories import NodeRepository

_ONLINE_HEARTBEAT_MAX_AGE = timedelta(seconds=90)


class NodeService:
    """Coordinate node board reads and center-config writes."""

    def __init__(self, *, nodes: NodeRepository) -> None:
        """Bind service to the node repository used by IM routes and WS handlers."""
        self._nodes = nodes

    def list_nodes(self, *, connected_node_ids: set[str] | None = None) -> list[NodeStatus]:
        """List node snapshots with read-time online/offline projection."""
        nodes = self._nodes.list_nodes()
        return [
            self._project_effective_node_status(
                node=node,
                connected_node_ids=connected_node_ids,
            )
            for node in nodes
        ]

    def get_node(self, *, node_id: str) -> NodeStatus | None:
        """Return one node snapshot, or None when missing."""
        return self._nodes.get_node(node_id=node_id)

    def update_node_config(
        self,
        *,
        node_id: str,
        alias: str | None,
        relay_enabled: bool | None,
        reporting_enabled: bool | None,
    ) -> NodeStatus:
        """Update one node's center config knobs."""
        return self._nodes.update_node_config(
            node_id=node_id,
            alias=alias,
            relay_enabled=relay_enabled,
            reporting_enabled=reporting_enabled,
        )

    def _project_effective_node_status(
        self,
        *,
        node: NodeStatus,
        connected_node_ids: set[str] | None,
    ) -> NodeStatus:
        """Project one persisted row into read-time effective status."""
        if node.status != "online":
            return node
        if not _is_heartbeat_fresh(node.last_heartbeat_at):
            return replace(node, status="offline")
        if connected_node_ids is not None and node.node_id not in connected_node_ids:
            return replace(node, status="offline")
        return node


def _is_heartbeat_fresh(raw_value: str) -> bool:
    """Return whether one heartbeat timestamp is still within the online window."""
    heartbeat_at = _parse_utc_timestamp(raw_value)
    if heartbeat_at is None:
        return False
    return datetime.now(timezone.utc) - heartbeat_at <= _ONLINE_HEARTBEAT_MAX_AGE


def _parse_utc_timestamp(raw_value: str) -> datetime | None:
    """Parse one persisted timestamp into UTC datetime."""
    value = raw_value.strip()
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
