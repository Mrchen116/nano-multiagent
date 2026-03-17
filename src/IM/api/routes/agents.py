"""Agent configuration routes for IM HTTP APIs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.model_registry import list_provider_models
from agent.core.skills.discovery import default_skill_search_roots
from agent.core.skills.registry import SkillRegistry
from agent.platform.config.resolver import ConfigResolver
from agent.platform.tools.loader import build_tool_registry
from agent.products.personal_assistant.profile import PERSONAL_ASSISTANT_PROFILE
from IM.api.deps import get_config_service, get_gateway_handler
from IM.application.config_service import ConfigService
from IM.domain.models import AgentProfile
from IM.ws.gateway_handler import GatewayHandler
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
    workspace_root: str
    workspace_is_default: bool
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
    workspace_root: str | None = None
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
    workspace_root: str | None = None


class AgentSummaryResponse(BaseModel):
    """Compact agent list item for settings pages."""

    agent_id: str
    owner_id: str
    display_name: str
    description: str
    profile_version: int
    default_model: str | None
    workspace_root: str
    workspace_is_default: bool
    bound_nodes: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class AllowlistOptionResponse(BaseModel):
    """One selectable allowlist option exposed to the IM settings UI."""

    name: str
    description: str = ""


class AgentAllowlistOptionsResponse(BaseModel):
    """Selectable skills, tools, models, and product-owned defaults for the settings UI."""

    skills: list[AllowlistOptionResponse] = Field(default_factory=list)
    tools: list[AllowlistOptionResponse] = Field(default_factory=list)
    model_options: list[str] = Field(default_factory=list)
    platform_default_model: str | None = None
    default_system_prompt: str = ""


def _discover_repo_root(start_dir: Path) -> Path | None:
    """Resolve the canonical repository root for the running checkout or worktree."""
    current = start_dir.expanduser().resolve(strict=False)
    while True:
        dot_git_path = current / ".git"
        if dot_git_path.is_dir():
            return current
        if dot_git_path.is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _resolve_repo_root() -> Path:
    """Return the repository root used for skill/tool discovery."""
    fallback = Path(__file__).resolve().parents[4]
    return _discover_repo_root(Path(__file__).resolve()) or fallback


def _product_source_root() -> Path:
    """Return the personal_assistant product source directory."""
    return Path(__file__).resolve().parents[3] / "agent" / "products" / "personal_assistant"


def _build_allowlist_config_resolver(*, repo_root: Path) -> ConfigResolver:
    """Build the product-aware config resolver used by allowlist option discovery."""
    return ConfigResolver(profile=PERSONAL_ASSISTANT_PROFILE, workspace_root=repo_root)


def _list_available_skill_options() -> list[AllowlistOptionResponse]:
    """List current selectable skills for the agent settings UI."""
    repo_root = _resolve_repo_root()
    product_root = _product_source_root()
    config_resolver = _build_allowlist_config_resolver(repo_root=repo_root)
    registry = SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=repo_root,
            config_resolver=config_resolver,
            product_skill_root=product_root / "skills",
        )
    )
    return [
        AllowlistOptionResponse(name=skill.name, description=skill.description)
        for skill in registry.list_skills(refresh=True)
    ]


def _list_available_tool_options() -> list[AllowlistOptionResponse]:
    """List current selectable tools for the agent settings UI."""
    repo_root = _resolve_repo_root()
    product_root = _product_source_root()
    config_resolver = _build_allowlist_config_resolver(repo_root=repo_root)
    registry = build_tool_registry(
        repo_root=repo_root,
        config_resolver=config_resolver,
        product_tool_dir=product_root / "tools",
    )
    return [
        AllowlistOptionResponse(name=spec.name, description=spec.description)
        for spec in sorted(registry.list_specs(), key=lambda spec: spec.name)
    ]


def _list_available_models() -> list[str]:
    """List selectable models for the currently configured provider."""
    llm_config = LLMFactoryConfig.from_env()
    return [metadata.model for metadata in list_provider_models(llm_config.provider)]


def _platform_default_model() -> str | None:
    """Return the current platform default model shown in settings."""
    llm_config = LLMFactoryConfig.from_env()
    available_models = {metadata.model for metadata in list_provider_models(llm_config.provider)}
    if llm_config.model in available_models:
        return llm_config.model
    return next(iter(sorted(available_models)), None)


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
        workspace_root=service.workspace_root_for_profile(profile),
        workspace_is_default=service.workspace_is_default_for_profile(profile),
        profile_version=profile.profile_version,
        bound_nodes=service.list_bound_nodes(agent_id=profile.agent_id),
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
        display_name=profile.display_name,
        description=profile.description,
        profile_version=profile.profile_version,
        default_model=profile.default_model,
        workspace_root=service.workspace_root_for_profile(profile),
        workspace_is_default=service.workspace_is_default_for_profile(profile),
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
            workspace_root=payload.workspace_root,
            node_id=payload.node_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = status.HTTP_409_CONFLICT if str(exc) == "agent_id already exists" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return to_agent_config_response(created, service=service)


@router.get("/im/v1/agents", response_model=list[AgentSummaryResponse])
def list_agents(service: ConfigService = Depends(get_config_service)) -> list[AgentSummaryResponse]:
    """List runtime-selectable agents for the current IM workspace."""
    return [to_agent_summary_response(item, service=service) for item in service.list_runtime_selectable_profiles()]


@router.get("/im/v1/agents/allowlist-options", response_model=AgentAllowlistOptionsResponse)
def get_agent_allowlist_options() -> AgentAllowlistOptionsResponse:
    """Return current selectable skills, tools, models, and product-owned defaults for agent settings."""
    return AgentAllowlistOptionsResponse(
        skills=_list_available_skill_options(),
        tools=_list_available_tool_options(),
        model_options=_list_available_models(),
        platform_default_model=_platform_default_model(),
        default_system_prompt=PERSONAL_ASSISTANT_PROFILE.default_system_prompt or "",
    )


@router.get("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
async def get_agent_config(
    agent_id: str,
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentConfigResponse:
    """Return one agent configuration profile, preferring a live gateway snapshot when available."""
    profile = service.get_profile(agent_id=agent_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    for node_id in service.list_bound_nodes(agent_id=agent_id):
        payload = await gateway_handler.request_agent_config(target_node_id=node_id, agent_id=agent_id)
        if not isinstance(payload, dict):
            continue
        profile = _merge_live_agent_profile(profile, payload)
        break
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
            workspace_root=payload.workspace_root,
        )
    except AgentProfileVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return to_agent_config_response(updated, service=service)
