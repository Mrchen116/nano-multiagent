"""Agent configuration and capability routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from IM.api.deps import get_config_service, get_gateway_handler
from IM.application.config_service import ConfigService
from IM.domain.models import AgentProfile
from IM.infra.repositories import AgentProfileVersionConflictError
from IM.ws.gateway_handler import GatewayHandler

router = APIRouter(tags=["agents"])


class AgentConfigResponse(BaseModel):
    """Serialized agent profile returned by config APIs."""

    agent_id: str
    owner_id: str
    node_id: str | None
    display_name: str
    description: str
    system_prompt: str
    skills: list[str]
    tool_allowlist: list[str]
    group_reply_policy: str
    default_model: str | None
    workspace_root: str
    workspace_is_default: bool
    profile_version: int
    updated_at: str | None = None


class UpdateAgentConfigRequest(BaseModel):
    """Request payload for updating one agent profile."""

    profile_version: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    group_reply_policy: str = Field(min_length=1)
    default_model: str | None = None


class AgentSummaryResponse(BaseModel):
    """Compact agent list item for settings pages."""

    agent_id: str
    owner_id: str
    node_id: str | None
    display_name: str
    description: str
    profile_version: int
    default_model: str | None
    workspace_root: str
    workspace_is_default: bool
    updated_at: str | None = None


class AgentCapabilitiesResponse(BaseModel):
    """Node-backed runtime capability data for one agent workspace."""

    agent_id: str
    node_id: str
    workspace_root: str
    models: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


def to_agent_config_response(profile: AgentProfile, *, service: ConfigService) -> AgentConfigResponse:
    """Convert a domain profile to the config response model."""
    return AgentConfigResponse(
        agent_id=profile.agent_id,
        owner_id=profile.owner_id,
        node_id=profile.node_id,
        display_name=profile.display_name,
        description=profile.description,
        system_prompt=profile.system_prompt,
        skills=profile.skills,
        tool_allowlist=profile.tool_allowlist,
        group_reply_policy=profile.group_reply_policy,
        default_model=profile.default_model,
        workspace_root=service.workspace_root_for_profile(profile),
        workspace_is_default=service.workspace_is_default_for_profile(profile),
        profile_version=profile.profile_version,
        updated_at=service.get_updated_at(agent_id=profile.agent_id),
    )


def _merge_live_agent_profile(profile: AgentProfile, payload: dict[str, object]) -> AgentProfile:
    """Overlay one live gateway snapshot onto the persisted IM mirror for read APIs."""
    display_name = payload.get("display_name")
    system_prompt = payload.get("system_prompt")
    skills = payload.get("skills")
    tool_allowlist = payload.get("tool_allowlist")
    group_reply_policy = payload.get("group_reply_policy")
    default_model = payload.get("default_model")
    workspace_root = payload.get("workspace_root")
    return AgentProfile(
        agent_id=profile.agent_id,
        owner_id=profile.owner_id,
        node_id=profile.node_id,
        display_name=display_name if isinstance(display_name, str) and display_name.strip() else profile.display_name,
        description=profile.description,
        system_prompt=system_prompt if isinstance(system_prompt, str) else profile.system_prompt,
        skills=[item for item in skills if isinstance(item, str)] if isinstance(skills, list) else profile.skills,
        tool_allowlist=[item for item in tool_allowlist if isinstance(item, str)] if isinstance(tool_allowlist, list) else profile.tool_allowlist,
        group_reply_policy=(
            group_reply_policy if isinstance(group_reply_policy, str) and group_reply_policy.strip() else profile.group_reply_policy
        ),
        default_model=default_model if isinstance(default_model, str) or default_model is None else profile.default_model,
        workspace_root=workspace_root if isinstance(workspace_root, str) and workspace_root.strip() else profile.workspace_root,
        profile_version=profile.profile_version,
    )


def to_agent_summary_response(profile: AgentProfile, *, service: ConfigService) -> AgentSummaryResponse:
    """Convert a domain profile to a compact agent list item."""
    return AgentSummaryResponse(
        agent_id=profile.agent_id,
        owner_id=profile.owner_id,
        node_id=profile.node_id,
        display_name=profile.display_name,
        description=profile.description,
        profile_version=profile.profile_version,
        default_model=profile.default_model,
        workspace_root=service.workspace_root_for_profile(profile),
        workspace_is_default=service.workspace_is_default_for_profile(profile),
        updated_at=service.get_updated_at(agent_id=profile.agent_id),
    )


@router.get("/im/v1/agents", response_model=list[AgentSummaryResponse])
def list_agents(service: ConfigService = Depends(get_config_service)) -> list[AgentSummaryResponse]:
    """List runtime-selectable agents for the current IM workspace."""
    return [to_agent_summary_response(item, service=service) for item in service.list_runtime_selectable_profiles()]


@router.get("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
async def get_agent_config(
    agent_id: str,
    source: str = Query(default="live"),
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentConfigResponse:
    """Return one agent configuration profile.

    `source=live` prefers a live Gateway snapshot when available.
    `source=mirror` forces the IM-stored mirror row so Gateway config.sync fetches do not reflect stale local state back to themselves.
    """
    profile = service.get_profile(agent_id=agent_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    if source == "mirror":
        return to_agent_config_response(profile, service=service)
    if source != "live":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="source must be live or mirror")
    if profile.node_id:
        payload = await gateway_handler.request_agent_config(target_node_id=profile.node_id, agent_id=agent_id)
        if isinstance(payload, dict):
            profile = _merge_live_agent_profile(profile, payload)
    return to_agent_config_response(profile, service=service)


@router.get("/im/v1/agents/{agent_id}/capabilities", response_model=AgentCapabilitiesResponse)
async def get_agent_capabilities(
    agent_id: str,
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentCapabilitiesResponse:
    """Resolve runtime capabilities for one agent from its owning node."""
    profile = service.get_profile(agent_id=agent_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    if profile.node_id is None or not profile.node_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent_id is not bound to a node")
    workspace_root = service.workspace_root_for_profile(profile)
    payload = await gateway_handler.request_agent_capabilities(
        target_node_id=profile.node_id,
        agent_id=agent_id,
        workspace_root=workspace_root,
    )
    if payload is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="target_node_id is not connected")
    return AgentCapabilitiesResponse(
        agent_id=agent_id,
        node_id=profile.node_id,
        workspace_root=workspace_root,
        models=_coerce_string_list(payload.get("models")),
        skills=_coerce_string_list(payload.get("skills")),
        tools=_coerce_string_list(payload.get("tools")),
    )


@router.patch("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
def update_agent_config(
    agent_id: str,
    payload: UpdateAgentConfigRequest,
    service: ConfigService = Depends(get_config_service),
) -> AgentConfigResponse:
    """Update one agent configuration profile with optimistic locking."""
    try:
        updated = service.update_profile(
            agent_id=agent_id,
            profile_version=payload.profile_version,
            display_name=payload.display_name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            skills=payload.skills,
            tool_allowlist=payload.tool_allowlist,
            group_reply_policy=payload.group_reply_policy,
            default_model=payload.default_model,
            workspace_root=None,
        )
    except AgentProfileVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return to_agent_config_response(updated, service=service)


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
