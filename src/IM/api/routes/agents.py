"""Agent configuration routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_config_service
from IM.application.config_service import ConfigService
from IM.domain.models import AgentProfile
from IM.infra.repositories import AgentProfileVersionConflictError

router = APIRouter(tags=["agents"])


class AgentConfigResponse(BaseModel):
    """Serialized agent profile returned by config APIs."""

    agent_id: str
    owner_id: str
    display_name: str
    description: str
    system_prompt: str
    skills: list[str]
    tool_allowlist: list[str]
    group_reply_policy: str
    default_model: str | None
    profile_version: int
    bound_nodes: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class CreateAgentRequest(BaseModel):
    """Request payload for creating one agent profile."""

    agent_id: str = Field(min_length=1)
    owner_id: str = ""
    display_name: str = Field(min_length=1)
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    group_reply_policy: str = Field(min_length=1)
    default_model: str | None = None
    node_id: str | None = None


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
    display_name: str
    description: str
    profile_version: int
    default_model: str | None
    bound_nodes: list[str] = Field(default_factory=list)
    updated_at: str | None = None


def to_agent_config_response(profile: AgentProfile, *, service: ConfigService) -> AgentConfigResponse:
    """Convert a domain profile to the config response model."""
    return AgentConfigResponse(
        agent_id=profile.agent_id,
        owner_id=profile.owner_id,
        display_name=profile.display_name,
        description=profile.description,
        system_prompt=profile.system_prompt,
        skills=profile.skills,
        tool_allowlist=profile.tool_allowlist,
        group_reply_policy=profile.group_reply_policy,
        default_model=profile.default_model,
        profile_version=profile.profile_version,
        bound_nodes=service.list_bound_nodes(agent_id=profile.agent_id),
        updated_at=service.get_updated_at(agent_id=profile.agent_id),
    )


def to_agent_summary_response(profile: AgentProfile, *, service: ConfigService) -> AgentSummaryResponse:
    """Convert a domain profile to a compact agent list item."""
    return AgentSummaryResponse(
        agent_id=profile.agent_id,
        owner_id=profile.owner_id,
        display_name=profile.display_name,
        description=profile.description,
        profile_version=profile.profile_version,
        default_model=profile.default_model,
        bound_nodes=service.list_bound_nodes(agent_id=profile.agent_id),
        updated_at=service.get_updated_at(agent_id=profile.agent_id),
    )


@router.post("/im/v1/agents", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: CreateAgentRequest,
    service: ConfigService = Depends(get_config_service),
) -> AgentConfigResponse:
    """Create one agent profile bound to an optional node."""
    try:
        created = service.create_profile(
            agent_id=payload.agent_id,
            owner_id=payload.owner_id,
            display_name=payload.display_name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            skills=payload.skills,
            tool_allowlist=payload.tool_allowlist,
            group_reply_policy=payload.group_reply_policy,
            default_model=payload.default_model,
            node_id=payload.node_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_agent_config_response(created, service=service)


@router.get("/im/v1/agents", response_model=list[AgentSummaryResponse])
def list_agents(service: ConfigService = Depends(get_config_service)) -> list[AgentSummaryResponse]:
    """List all configured agents."""
    return [to_agent_summary_response(item, service=service) for item in service.list_profiles()]


@router.get("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
def get_agent_config(
    agent_id: str,
    service: ConfigService = Depends(get_config_service),
) -> AgentConfigResponse:
    """Return one agent configuration profile."""
    profile = service.get_profile(agent_id=agent_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    return to_agent_config_response(profile, service=service)


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
        )
    except AgentProfileVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_agent_config_response(updated, service=service)
