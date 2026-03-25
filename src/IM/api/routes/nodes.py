"""Node board and node center-config routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from IM.api.deps import get_gateway_handler, get_node_service
from IM.application.node_service import NodeService
from IM.domain.models import NodeStatus
from IM.ws.gateway_handler import GatewayHandler

router = APIRouter(tags=["nodes"])


class NodeResponse(BaseModel):
    """Serialized node board item returned by node APIs."""

    node_id: str
    owner_id: str
    node_name: str
    status: str
    last_heartbeat_at: str
    agent_count: int
    version: str
    relay_enabled: bool
    reporting_enabled: bool
    alias: str | None
    last_error: str | None


class UpdateNodeConfigRequest(BaseModel):
    """Request payload for updating one node center-config object."""

    alias: str | None = None
    relay_enabled: bool | None = None
    reporting_enabled: bool | None = None


def to_node_response(node: NodeStatus) -> NodeResponse:
    """Convert a node domain model to the API response model."""
    return NodeResponse(
        node_id=node.node_id,
        owner_id=node.owner_id,
        node_name=node.node_name,
        status=node.status,
        last_heartbeat_at=node.last_heartbeat_at,
        agent_count=node.agent_count,
        version=node.version,
        relay_enabled=node.relay_enabled,
        reporting_enabled=node.reporting_enabled,
        alias=node.alias,
        last_error=node.last_error,
    )


@router.get("/im/v1/nodes", response_model=list[NodeResponse])
async def list_nodes(
    service: NodeService = Depends(get_node_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> list[NodeResponse]:
    """List node board snapshots with canonical online/offline/degraded status."""
    connected_node_ids = await gateway_handler.list_connected_node_ids()
    return [to_node_response(item) for item in service.list_nodes(connected_node_ids=connected_node_ids)]


@router.patch("/im/v1/nodes/{node_id}/config", response_model=NodeResponse)
def update_node_config(
    node_id: str,
    payload: UpdateNodeConfigRequest,
    service: NodeService = Depends(get_node_service),
) -> NodeResponse:
    """Update one node's center-config knobs and return the new snapshot."""
    try:
        updated = service.update_node_config(
            node_id=node_id,
            alias=payload.alias,
            relay_enabled=payload.relay_enabled,
            reporting_enabled=payload.reporting_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_node_response(updated)
