"""Node board, capability, and node-scoped agent creation routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_config_service, get_gateway_handler, get_node_service
from IM.api.routes.agents import AgentCapabilitiesResponse, AgentConfigResponse, to_agent_config_response
from IM.application.config_service import ConfigService
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


class CreateNodeAgentRequest(BaseModel):
    """Request payload for creating one agent on a specific node."""

    agent_id: str = Field(min_length=1)
    owner_id: str = ""
    display_name: str = Field(min_length=1)
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    group_reply_policy: str = Field(min_length=1)
    default_model: str | None = None
    workspace_root: str | None = None


class NodeCapabilitiesResponse(BaseModel):
    """Last node-reported runtime capability summary."""

    node_id: str
    models: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    platform_default_model: str | None = None
    default_system_prompt: str = ""


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


@router.get("/im/v1/nodes/{node_id}/capabilities", response_model=NodeCapabilitiesResponse)
def get_node_capabilities(
    node_id: str,
    service: NodeService = Depends(get_node_service),
) -> NodeCapabilitiesResponse:
    """Return the last runtime capability summary reported by one node."""
    try:
        capabilities = service.get_node_capabilities(node_id=node_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return NodeCapabilitiesResponse(
        node_id=node_id,
        models=_coerce_string_list(capabilities.get("models")),
        skills=_coerce_string_list(capabilities.get("skills")),
        tools=_coerce_string_list(capabilities.get("tools")),
        platform_default_model=_coerce_optional_text(capabilities.get("platform_default_model"), fallback=None),
        default_system_prompt=_coerce_text(capabilities.get("default_system_prompt"), fallback=""),
    )


@router.post("/im/v1/nodes/{node_id}/agents", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_node_agent(
    node_id: str,
    payload: CreateNodeAgentRequest,
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentConfigResponse:
    """Create one agent under the requested node using node-managed workspace allocation."""
    created_payload = await gateway_handler.request_agent_create(
        target_node_id=node_id,
        payload={
            "agent_id": payload.agent_id,
            "display_name": payload.display_name,
            "description": payload.description,
            "system_prompt": payload.system_prompt,
            "skills": payload.skills,
            "tool_allowlist": payload.tool_allowlist,
            "group_reply_policy": payload.group_reply_policy,
            "default_model": payload.default_model,
            "workspace_root": payload.workspace_root,
        },
    )
    if created_payload is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="target_node_id is not connected")
    workspace_root = created_payload.get("workspace_root")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="node did not return workspace_root")
    try:
        created = service.create_profile(
            agent_id=payload.agent_id,
            owner_id=payload.owner_id,
            node_id=node_id,
            display_name=_coerce_text(created_payload.get("display_name"), fallback=payload.display_name),
            description=_coerce_text(created_payload.get("description"), fallback=payload.description),
            system_prompt=_coerce_text(created_payload.get("system_prompt"), fallback=payload.system_prompt),
            skills=_coerce_string_list(created_payload.get("skills"), fallback=payload.skills),
            tool_allowlist=_coerce_string_list(created_payload.get("tool_allowlist"), fallback=payload.tool_allowlist),
            group_reply_policy=_coerce_text(created_payload.get("group_reply_policy"), fallback=payload.group_reply_policy),
            default_model=_coerce_optional_text(created_payload.get("default_model"), fallback=payload.default_model),
            workspace_root=workspace_root,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = status.HTTP_409_CONFLICT if str(exc) == "agent_id already exists" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return to_agent_config_response(created, service=service)


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


def _coerce_string_list(value: object, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return list(fallback or [])


def _coerce_text(value: object, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _coerce_optional_text(value: object, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return fallback
