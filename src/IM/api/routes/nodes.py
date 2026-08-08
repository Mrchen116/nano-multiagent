"""Node board, capability, and node-scoped agent creation routes for IM HTTP APIs."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from IM.api.deps import (
    current_user,
    get_agent_create_lock,
    get_config_service,
    get_node_service,
)
from IM.api.routes.agents import (
    AgentConfigResponse,
    AllowlistOptionResponse,
    FeatureCapabilityResponse,
    ModelOptionResponse,
    PromptPreviewResponse,
    _coerce_feature_list,
    coerce_allowlist_options,
    coerce_model_options,
    to_agent_config_response,
)
from IM.application.config_service import ConfigService
from IM.application.node_service import NodeService
from IM.api.deps import get_gateway_control, get_gateway_sessions
from IM.ws.gateway.control import GatewayControl
from IM.ws.gateway.sessions import GatewaySessions
from IM.domain.models import NodeStatus, User

router = APIRouter(tags=["nodes"])


class NodePromptPreviewRequest(BaseModel):
    """Request body for the node-scoped prompt-preview endpoint.

    Args:
        features: Per-agent feature flags (key → bool) to preview with.
        custom_prompt: Optional user-supplied text supplement.
        tool_ids: Tool names to treat as active for the preview turn.
        scenario: Conversation type hint; defaults to ``direct``.
        skill_ids: Skill names to resolve from workspace.  Forwarded to kernel.
        agent_id_hint: Optional agent ID whose managed workspace_root will be
            derived and forwarded to kernel.  When absent, workspace_root is
            empty and the kernel uses its cwd placeholder.
    """

    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    scenario: str = "direct"
    skill_ids: list[str] = Field(default_factory=list)
    agent_id_hint: str | None = None
    workspace_mode: Literal["default", "custom"] = "default"
    workspace_root: str | None = None


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
    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    skills: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    group_reply_policy: str = Field(min_length=1)
    default_model: str | None = None
    workspace_root: str | None = None
    confirm_existing_workspace: bool = False


class NodeCapabilitiesResponse(BaseModel):
    """网关节点当场解析的运行时能力（打开新建 Agent 页时按需拉取）。"""

    node_id: str
    models: list[ModelOptionResponse] = Field(default_factory=list)
    skills: list[AllowlistOptionResponse] = Field(default_factory=list)
    tools: list[AllowlistOptionResponse] = Field(default_factory=list)
    platform_default_model: str | None = None
    # feat-379-M6 (ISSUE-1): expose feature toggles so agent-create page can render
    # the Features section without a per-agent capabilities call (agent not yet created).
    features: list[FeatureCapabilityResponse] = Field(default_factory=list)


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
    user: User = Depends(current_user),
    service: NodeService = Depends(get_node_service),
    gateway_sessions: GatewaySessions = Depends(get_gateway_sessions),
) -> list[NodeResponse]:
    """List node board snapshots visible to the caller's tenant (+ ownerless fresh nodes)."""
    connected_node_ids = await gateway_sessions.list_connected_node_ids()
    return [
        to_node_response(item)
        for item in service.list_nodes_for_owner(
            owner_id=user.owner_id, connected_node_ids=connected_node_ids
        )
    ]


@router.get(
    "/im/v1/nodes/{node_id}/capabilities", response_model=NodeCapabilitiesResponse
)
async def get_node_capabilities(
    node_id: str,
    user: User = Depends(current_user),
    service: NodeService = Depends(get_node_service),
    gateway_handler: GatewayControl = Depends(get_gateway_control),
) -> NodeCapabilitiesResponse:
    """向已连接的网关节点当场请求运行时能力（不在 IM 库中缓存目录数据）。"""
    if service.get_node_for_owner(node_id=node_id, owner_id=user.owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="node_id not found"
        )
    live = await gateway_handler.request_node_capabilities(target_node_id=node_id)
    if live is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="节点未连接或未能返回能力数据",
        )
    return NodeCapabilitiesResponse(
        node_id=node_id,
        models=coerce_model_options(live.get("models")),
        skills=coerce_allowlist_options(live.get("skills")),
        tools=coerce_allowlist_options(live.get("tools")),
        platform_default_model=_coerce_optional_text(
            live.get("platform_default_model"), fallback=None
        ),
        # feat-379-M6 (ISSUE-1): forward features from Gateway so agent-create page
        # can render the Features section without a per-agent capabilities call.
        features=_coerce_feature_list(live.get("features")),
    )


@router.post(
    "/im/v1/nodes/{node_id}/prompt-preview", response_model=PromptPreviewResponse
)
async def node_prompt_preview(
    node_id: str,
    payload: NodePromptPreviewRequest,
    user: User = Depends(current_user),
    service: NodeService = Depends(get_node_service),
    gateway_handler: GatewayControl = Depends(get_gateway_control),
) -> PromptPreviewResponse | JSONResponse:
    """Proxy a node-level prompt-preview request to the Gateway node (owner-scoped).

    feat-379-M9 (決策 11): Used by the agent-create page before an agent exists.
    Workspace intent is forwarded unchanged; only the target Gateway may interpret
    or canonicalize node-local paths.
    """
    if service.get_node_for_owner(node_id=node_id, owner_id=user.owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="node_id not found"
        )
    result = await gateway_handler.request_node_prompt_preview(
        target_node_id=node_id,
        features=payload.features,
        custom_prompt=payload.custom_prompt,
        tool_ids=payload.tool_ids,
        scenario=payload.scenario,
        workspace_mode=payload.workspace_mode,
        agent_id_hint=payload.agent_id_hint,
        workspace_root=payload.workspace_root,
        skill_ids=payload.skill_ids,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="target_node_id is not connected",
        )
    error_payload = result.get("error")
    if isinstance(error_payload, dict):
        error_response = _workspace_error_response(error_payload)
        if error_response is not None:
            return error_response
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="node returned an invalid workspace error",
        )
    raw_prompt = result.get("prompt")
    prompt = raw_prompt if isinstance(raw_prompt, str) else ""
    raw_count = result.get("section_count")
    section_count = int(raw_count) if isinstance(raw_count, int) else 0
    return PromptPreviewResponse(prompt=prompt, section_count=section_count)


@router.post(
    "/im/v1/nodes/{node_id}/agents",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_node_agent(
    node_id: str,
    payload: CreateNodeAgentRequest,
    user: User = Depends(current_user),
    node_service: NodeService = Depends(get_node_service),
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayControl = Depends(get_gateway_control),
    create_lock: asyncio.Lock = Depends(get_agent_create_lock),
) -> AgentConfigResponse | JSONResponse:
    """Create one agent under the requested node using node-managed workspace allocation.

    The target node must belong to the authenticated tenant (or be an ownerless
    fresh runtime). Cross-tenant access returns 404.
    """
    if node_service.get_node_for_owner(node_id=node_id, owner_id=user.owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="node_id not found"
        )
    requested_skills: list[str] | None = payload.skills
    if "skills" not in payload.model_fields_set:
        requested_skills = None
        live_capabilities = await gateway_handler.request_node_capabilities(
            target_node_id=node_id
        )
        if live_capabilities is not None:
            requested_skills = _default_on_names(live_capabilities.get("skills"))
    async with create_lock:
        return await _create_node_agent_locked(
            node_id=node_id,
            payload=payload,
            user=user,
            service=service,
            gateway_handler=gateway_handler,
            requested_skills=requested_skills,
        )


async def _create_node_agent_locked(
    *,
    node_id: str,
    payload: CreateNodeAgentRequest,
    user: User,
    service: ConfigService,
    gateway_handler: GatewayControl,
    requested_skills: list[str] | None,
) -> AgentConfigResponse | JSONResponse:
    """Create one Agent while the app-scoped uniqueness lock is held."""
    existing = service.get_profile(agent_id=payload.agent_id)
    seeded_claim_candidate = (
        existing is not None
        and not existing.owner_id.strip()
        and existing.node_id == node_id
        and existing.workspace_root is not None
        and existing.workspace_is_default is not None
    )
    if existing is not None and not seeded_claim_candidate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="agent_id already exists"
        )
    create_payload: dict[str, object] = {
        "agent_id": payload.agent_id,
        "display_name": payload.display_name,
        "description": payload.description,
        "features": payload.features,
        "custom_prompt": payload.custom_prompt,
        "tool_allowlist": payload.tool_allowlist,
        "group_reply_policy": payload.group_reply_policy,
        "default_model": payload.default_model,
        "workspace_root": payload.workspace_root,
        "confirm_existing_workspace": payload.confirm_existing_workspace,
    }
    if requested_skills is not None:
        create_payload["skills"] = requested_skills
    created_payload = await gateway_handler.request_agent_create(
        target_node_id=node_id,
        payload=create_payload,
    )
    if created_payload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="target_node_id is not connected",
        )
    error_payload = created_payload.get("error")
    if isinstance(error_payload, dict):
        error_response = _workspace_error_response(error_payload)
        if error_response is not None:
            return error_response
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="node returned an invalid workspace error",
        )
    workspace_root = created_payload.get("workspace_root")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="node did not return workspace_root",
        )
    workspace_is_default = created_payload.get("workspace_is_default")
    resolved_workspace_is_default = (
        workspace_is_default if isinstance(workspace_is_default, bool) else None
    )
    display_name = _coerce_text(
        created_payload.get("display_name"), fallback=payload.display_name
    )
    description = _coerce_text(
        created_payload.get("description"), fallback=payload.description
    )
    skills = _coerce_string_list(
        created_payload.get("skills"), fallback=requested_skills
    )
    tool_allowlist = _coerce_string_list(
        created_payload.get("tool_allowlist"), fallback=payload.tool_allowlist
    )
    group_reply_policy = _coerce_text(
        created_payload.get("group_reply_policy"),
        fallback=payload.group_reply_policy,
    )
    default_model = _coerce_optional_text(
        created_payload.get("default_model"), fallback=payload.default_model
    )
    features = _coerce_bool_dict(
        created_payload.get("features"), fallback=payload.features
    )
    custom_prompt = _coerce_optional_text(
        created_payload.get("custom_prompt"), fallback=payload.custom_prompt
    )
    try:
        if seeded_claim_candidate:
            assert existing is not None
            if (
                workspace_root != existing.workspace_root
                or resolved_workspace_is_default != existing.workspace_is_default
                or display_name != payload.display_name
                or (
                    payload.workspace_root is not None
                    and payload.workspace_root != workspace_root
                )
            ):
                raise ValueError("agent_id already exists")
            assert resolved_workspace_is_default is not None
            created = service.claim_seeded_profile(
                agent_id=payload.agent_id,
                owner_id=user.owner_id,
                node_id=node_id,
                expected_workspace_root=workspace_root,
                expected_workspace_is_default=resolved_workspace_is_default,
                display_name=display_name,
                description=description,
                skills=skills,
                tool_allowlist=tool_allowlist,
                group_reply_policy=group_reply_policy,
                default_model=default_model,
                features=features,
                custom_prompt=custom_prompt,
            )
        else:
            created = service.create_profile(
                agent_id=payload.agent_id,
                owner_id=user.owner_id,
                node_id=node_id,
                display_name=display_name,
                description=description,
                skills=skills,
                tool_allowlist=tool_allowlist,
                group_reply_policy=group_reply_policy,
                default_model=default_model,
                workspace_root=workspace_root,
                workspace_is_default=resolved_workspace_is_default,
                features=features,
                custom_prompt=custom_prompt,
            )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if str(exc) == "agent_id already exists"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return to_agent_config_response(created, service=service)


def _workspace_error_response(error: dict[str, object]) -> JSONResponse | None:
    code = error.get("code")
    detail = error.get("detail")
    if not isinstance(code, str) or not isinstance(detail, str):
        return None
    conflict_codes = {
        "agent_id_already_exists",
        "workspace_confirmation_required",
        "workspace_already_assigned",
    }
    validation_codes = {
        "workspace_parent_missing",
        "workspace_parent_unusable",
        "workspace_target_not_directory",
        "workspace_initialization_failed",
    }
    if code not in conflict_codes | validation_codes:
        return None
    body: dict[str, object] = {"code": code, "detail": detail}
    agent_id = error.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        body["agent_id"] = agent_id
    return JSONResponse(
        status_code=(
            status.HTTP_409_CONFLICT
            if code in conflict_codes
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        ),
        content=body,
    )


@router.patch("/im/v1/nodes/{node_id}/config", response_model=NodeResponse)
def update_node_config(
    node_id: str,
    payload: UpdateNodeConfigRequest,
    user: User = Depends(current_user),
    service: NodeService = Depends(get_node_service),
) -> NodeResponse:
    """Update one node's center-config knobs and return the new snapshot (owner-scoped)."""
    if service.get_node_for_owner(node_id=node_id, owner_id=user.owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="node_id not found"
        )
    try:
        updated = service.update_node_config(
            node_id=node_id,
            alias=payload.alias,
            relay_enabled=payload.relay_enabled,
            reporting_enabled=payload.reporting_enabled,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return to_node_response(updated)


def _coerce_string_list(value: object, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return list(fallback or [])


def _coerce_bool_dict(value: object, *, fallback: dict[str, bool]) -> dict[str, bool]:
    if not isinstance(value, dict):
        return dict(fallback)
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, bool)
    }


def _default_on_names(value: object) -> list[str]:
    return [
        item.name for item in coerce_allowlist_options(value) if item.default_on is True
    ]


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
