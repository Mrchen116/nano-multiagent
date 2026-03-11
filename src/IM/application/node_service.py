"""Application service for IM node board and node config APIs."""

from IM.domain.models import NodeStatus
from IM.infra.repositories import NodeRepository


class NodeService:
    """Coordinate node board reads and center-config writes."""

    def __init__(self, *, nodes: NodeRepository) -> None:
        """Bind service to the node repository used by IM routes and WS handlers."""
        self._nodes = nodes

    def list_nodes(self) -> list[NodeStatus]:
        """List all node snapshots visible in IM storage order."""
        return self._nodes.list_nodes()

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
