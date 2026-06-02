"""Agent configuration and capability routes for IM HTTP APIs."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from typing import Any

from IM.api.deps import (
    current_user,
    get_config_service,
    get_gateway_handler,
    get_node_service,
    get_user_service,
)
from IM.application.config_service import ConfigService
from IM.application.node_service import NodeService
from IM.application.user_service import UserService
from IM.domain.models import AgentProfile, User
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
    # feat-379-M5 (ISSUE-2): per-agent feature flags and custom prompt supplement
    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    # feat-394: heartbeat configuration persisted as raw JSON string.
    # Shape: {"enabled": bool, "every": str, "active_hours": {...} | null}
    heartbeat_json: str | None = None
    # feat-394-M2: cron configuration persisted as raw JSON string.
    # Shape: {"enabled": bool}
    cron_json: str | None = None


class UpdateAgentConfigRequest(BaseModel):
    """Request payload for updating one agent profile."""

    model_config = {"extra": "ignore"}

    profile_version: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    group_reply_policy: str = Field(min_length=1)
    default_model: str | None = None
    # feat-379-M5 (ISSUE-2): per-agent feature flags and custom prompt supplement
    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    # feat-394: heartbeat configuration as raw JSON string (forwarded to gateway via ConfigSyncNotifier).
    # Also accepts ``heartbeat: {...}`` dict from the frontend (converted via model_validator below).
    heartbeat_json: str | None = None
    # feat-394-M2: cron configuration as raw JSON string.
    # Also accepts ``cron: {...}`` dict from the frontend (converted via model_validator below).
    cron_json: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_config_dicts(cls, data: Any) -> Any:
        """Convert frontend-style ``heartbeat: {...}`` and ``cron: {...}`` dicts to JSON strings.

        The frontend sends nested objects; the backend stores raw JSON strings so the gateway
        can forward them without re-serialization.  Both the raw-string form (from tests/gateway)
        and the dict form (from the UI) are accepted.
        """
        if not isinstance(data, dict):
            return data
        if "heartbeat" in data and data["heartbeat"] is not None and "heartbeat_json" not in data:
            data = dict(data)
            data["heartbeat_json"] = json.dumps(data.pop("heartbeat"))
        elif "heartbeat" in data:
            data = dict(data)
            data.pop("heartbeat", None)
        if "cron" in data and data["cron"] is not None and "cron_json" not in data:
            data = dict(data)
            data["cron_json"] = json.dumps(data.pop("cron"))
        elif "cron" in data:
            data = dict(data)
            data.pop("cron", None)
        return data


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
    # M17/R8-2: surface the IM user UUID that the WS event sender_user_id field
    # carries, so the chat workspace can map runtime sender → display_name on
    # `message.created` without an extra round-trip.
    user_id: str | None = None
    node_status: str | None = None


class AllowlistOptionResponse(BaseModel):
    """一项可选技能或工具的展示元数据（IM 设置页复用）。"""

    name: str
    description: str = ""


class FeatureCapabilityResponse(BaseModel):
    """One feature toggle descriptor as seen by the IM frontend.

    Matches the FEATURE_REGISTRY projection returned by the Gateway
    capabilities handler (feat-379 decision 7): IM forwards it verbatim.
    """

    key: str
    label_i18n: str
    help_i18n: str
    default_on: bool
    available: bool
    requires_tool: str | None = None


class AgentCapabilitiesResponse(BaseModel):
    """Node-backed runtime capability data for one agent workspace."""

    agent_id: str
    node_id: str
    workspace_root: str
    models: list[str] = Field(default_factory=list)
    skills: list[AllowlistOptionResponse] = Field(default_factory=list)
    tools: list[AllowlistOptionResponse] = Field(default_factory=list)
    platform_default_model: str | None = None
    default_system_prompt: str = ""
    # feat-379-M2: feature toggle projection from FEATURE_REGISTRY (decision 7)
    features: list[FeatureCapabilityResponse] = Field(default_factory=list)


def to_agent_config_response(
    profile: AgentProfile, *, service: ConfigService
) -> AgentConfigResponse:
    """Convert a domain profile to the config response model."""
    # feat-379-M5 (ISSUE-2): features/custom_prompt must be round-tripped so the
    # frontend can restore toggle state and custom text on page load.
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
        features=dict(profile.features) if profile.features else {},
        custom_prompt=profile.custom_prompt,
        heartbeat_json=profile.heartbeat_json,
        cron_json=profile.cron_json,
    )


def _merge_live_agent_profile(
    profile: AgentProfile, payload: dict[str, object]
) -> AgentProfile:
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
        display_name=display_name
        if isinstance(display_name, str) and display_name.strip()
        else profile.display_name,
        description=profile.description,
        system_prompt=system_prompt
        if isinstance(system_prompt, str)
        else profile.system_prompt,
        skills=[item for item in skills if isinstance(item, str)]
        if isinstance(skills, list)
        else profile.skills,
        tool_allowlist=[item for item in tool_allowlist if isinstance(item, str)]
        if isinstance(tool_allowlist, list)
        else profile.tool_allowlist,
        group_reply_policy=(
            group_reply_policy
            if isinstance(group_reply_policy, str) and group_reply_policy.strip()
            else profile.group_reply_policy
        ),
        default_model=default_model
        if isinstance(default_model, str) or default_model is None
        else profile.default_model,
        workspace_root=workspace_root
        if isinstance(workspace_root, str) and workspace_root.strip()
        else profile.workspace_root,
        profile_version=profile.profile_version,
        # feat-379-M7 (ISSUE-2): live gateway snapshots do not carry features/custom_prompt
        # (those are IM-owned fields set via PATCH, not reported back by the node).
        # Always inherit from the persisted profile so a live-merge never silently clears
        # user-configured feature overrides or custom_prompt.
        features=profile.features,
        custom_prompt=profile.custom_prompt,
    )


def to_agent_summary_response(
    profile: AgentProfile,
    *,
    service: ConfigService,
    user_service: UserService | None = None,
    node_status: str | None = None,
) -> AgentSummaryResponse:
    """Convert a domain profile to a compact agent list item."""
    # feat-340-M18 R9-1: rely on ConfigService.ensure_agent_user so legacy seeds
    # (agent profiles that pre-date the R9-1 fix and any profile written outside
    # the HTTP route) self-heal on first read. Falling back to ``user_service``
    # keeps unit tests that wire only the user service working.
    agent_user = service.ensure_agent_user(
        agent_id=profile.agent_id, display_name=profile.display_name
    )
    if agent_user is None and user_service is not None:
        agent_user = user_service.get_by_username(username=f"agent:{profile.agent_id}")
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
        user_id=agent_user.id if agent_user is not None else None,
        node_status=node_status,
    )


@router.get("/im/v1/agents", response_model=list[AgentSummaryResponse])
def list_agents(
    user: User = Depends(current_user),
    service: ConfigService = Depends(get_config_service),
    user_service: UserService = Depends(get_user_service),
    node_service: NodeService = Depends(get_node_service),
) -> list[AgentSummaryResponse]:
    """List runtime-selectable agents visible to the authenticated tenant."""
    nodes = {
        n.node_id: n.status
        for n in node_service.list_nodes_for_owner(owner_id=user.owner_id)
    }
    return [
        to_agent_summary_response(
            item,
            service=service,
            user_service=user_service,
            node_status=nodes.get(item.node_id) if item.node_id else None,
        )
        for item in service.list_runtime_selectable_profiles_for_owner(
            owner_id=user.owner_id
        )
    ]


@router.get("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
async def get_agent_config(
    agent_id: str,
    source: str = Query(default="live"),
    user: User = Depends(current_user),
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentConfigResponse:
    """Return one agent configuration profile, owner-scoped to the caller's tenant.

    `source=live` prefers a live Gateway snapshot when available.
    `source=mirror` forces the IM-stored mirror row so Gateway config.sync fetches do not reflect stale local state back to themselves.
    """
    profile = service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found"
        )
    if source == "mirror":
        return to_agent_config_response(profile, service=service)
    if source != "live":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source must be live or mirror",
        )
    if profile.node_id:
        payload = await gateway_handler.request_agent_config(
            target_node_id=profile.node_id, agent_id=agent_id
        )
        if isinstance(payload, dict):
            profile = _merge_live_agent_profile(profile, payload)
    return to_agent_config_response(profile, service=service)


@router.get(
    "/im/v1/agents/{agent_id}/capabilities", response_model=AgentCapabilitiesResponse
)
async def get_agent_capabilities(
    agent_id: str,
    user: User = Depends(current_user),
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> AgentCapabilitiesResponse:
    """Resolve runtime capabilities for one agent from its owning node (owner-scoped)."""
    profile = service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found"
        )
    if profile.node_id is None or not profile.node_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_id is not bound to a node",
        )
    workspace_root = service.workspace_root_for_profile(profile)
    payload = await gateway_handler.request_agent_capabilities(
        target_node_id=profile.node_id,
        agent_id=agent_id,
        workspace_root=workspace_root,
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="target_node_id is not connected",
        )
    raw_platform = payload.get("platform_default_model")
    platform_default: str | None = (
        raw_platform.strip()
        if isinstance(raw_platform, str) and raw_platform.strip()
        else None
    )
    raw_prompt = payload.get("default_system_prompt")
    default_system_prompt = raw_prompt if isinstance(raw_prompt, str) else ""
    # feat-379-M2: forward FEATURE_REGISTRY projection from Gateway verbatim
    features = _coerce_feature_list(payload.get("features"))
    return AgentCapabilitiesResponse(
        agent_id=agent_id,
        node_id=profile.node_id,
        workspace_root=workspace_root,
        models=_coerce_string_list(payload.get("models")),
        skills=coerce_allowlist_options(payload.get("skills")),
        tools=coerce_allowlist_options(payload.get("tools")),
        platform_default_model=platform_default,
        default_system_prompt=default_system_prompt,
        features=features,
    )


@router.patch("/im/v1/agents/{agent_id}/config", response_model=AgentConfigResponse)
def update_agent_config(
    agent_id: str,
    payload: UpdateAgentConfigRequest,
    user: User = Depends(current_user),
    service: ConfigService = Depends(get_config_service),
) -> AgentConfigResponse:
    """Update one agent configuration profile with optimistic locking (owner-scoped)."""
    if service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found"
        )
    try:
        # feat-379-M5 (ISSUE-2): pass features + custom_prompt through so they
        # are written to the DB and returned in the response.
        # feat-379-M7 (ISSUE-2): use `is not None` instead of falsy check.
        # An empty dict `{}` is falsy in Python but is a valid payload meaning
        # "the user cleared all feature overrides" — the old `if payload.features`
        # turned it into None, causing update_profile to fall back to the stored
        # value and silently drop the intentional update.
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
            features=payload.features if payload.features is not None else None,
            custom_prompt=payload.custom_prompt,
            heartbeat_json=payload.heartbeat_json,
            cron_json=payload.cron_json,
        )
    except AgentProfileVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return to_agent_config_response(updated, service=service)


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _coerce_feature_list(value: object) -> list[FeatureCapabilityResponse]:
    """Coerce raw Gateway features projection list into typed responses.

    Gateway returns list[dict] built from FEATURE_REGISTRY; IM forwards it
    verbatim after validation.  Missing or malformed items are silently dropped
    so old Gateway versions without feat-379-M2 still work.
    """
    if not isinstance(value, list):
        return []
    result: list[FeatureCapabilityResponse] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key:
            continue
        label = item.get("label_i18n", "")
        help_text = item.get("help_i18n", "")
        default_on = bool(item.get("default_on", False))
        available = bool(item.get("available", True))
        requires_tool = item.get("requires_tool")
        result.append(
            FeatureCapabilityResponse(
                key=key,
                label_i18n=label if isinstance(label, str) else "",
                help_i18n=help_text if isinstance(help_text, str) else "",
                default_on=default_on,
                available=available,
                requires_tool=requires_tool if isinstance(requires_tool, str) else None,
            )
        )
    return result


def coerce_allowlist_options(value: object) -> list[AllowlistOptionResponse]:
    """兼容历史心跳里 skills/tools 只为 string 列表；新节点上报 ``{name, description}`` 对象。"""
    if not isinstance(value, list):
        return []
    result: list[AllowlistOptionResponse] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
            if name:
                result.append(AllowlistOptionResponse(name=name, description=""))
            continue
        if isinstance(item, dict):
            raw_name = item.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            raw_desc = item.get("description")
            desc = raw_desc.strip() if isinstance(raw_desc, str) else ""
            result.append(
                AllowlistOptionResponse(name=raw_name.strip(), description=desc)
            )
    return result


# ---------------------------------------------------------------------------
# Prompt preview proxy (feat-379-M2 R5)
# ---------------------------------------------------------------------------


class PromptPreviewRequest(BaseModel):
    """Request body forwarded to agent Gateway /v1/prompt-preview.

    Args:
        features: Per-agent feature flags (key → bool) to preview with.
        custom_prompt: Optional user-supplied text supplement.
        tool_ids: Tool names to treat as active for the preview turn.
        scenario: Conversation type hint; defaults to ``direct``.
        skill_ids: Skill names to resolve from workspace.  forwarded to kernel.
    """

    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    scenario: str = "direct"
    skill_ids: list[str] = Field(default_factory=list)


class PromptPreviewResponse(BaseModel):
    """Assembled prompt preview returned from the Gateway."""

    prompt: str
    section_count: int


@router.post(
    "/im/v1/agents/{agent_id}/prompt-preview", response_model=PromptPreviewResponse
)
async def agent_prompt_preview(
    agent_id: str,
    payload: PromptPreviewRequest,
    user: User = Depends(current_user),
    service: ConfigService = Depends(get_config_service),
    gateway_handler: GatewayHandler = Depends(get_gateway_handler),
) -> PromptPreviewResponse:
    """Proxy a prompt-preview request to the owning Gateway node (owner-scoped).

    feat-379-M2 R5: IM acts as a pass-through; Gateway calls agent HTTP
    /v1/prompt-preview and returns the assembled system-prompt preview.
    The IM route exists so the frontend can call a single authenticated
    IM endpoint instead of calling the agent HTTP API directly.
    """
    profile = service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found"
        )
    if profile.node_id is None or not profile.node_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_id is not bound to a node",
        )
    workspace_root = service.workspace_root_for_profile(profile)
    result = await gateway_handler.request_prompt_preview(
        target_node_id=profile.node_id,
        agent_id=agent_id,
        workspace_root=workspace_root,
        features=payload.features,
        custom_prompt=payload.custom_prompt,
        tool_ids=payload.tool_ids,
        scenario=payload.scenario,
        skill_ids=payload.skill_ids,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="target_node_id is not connected",
        )
    raw_prompt = result.get("prompt")
    prompt = raw_prompt if isinstance(raw_prompt, str) else ""
    raw_count = result.get("section_count")
    section_count = int(raw_count) if isinstance(raw_count, int) else 0
    return PromptPreviewResponse(prompt=prompt, section_count=section_count)


# ---------------------------------------------------------------------------
# feat-394-M3 WARNING-3: cron jobs list + delete (Scenario: 配置页查看并手动删除任务)
# ---------------------------------------------------------------------------

_CRON_JOBS_PATH = ".nanoassistant/cron/jobs.json"


class CronJobSummary(BaseModel):
    """Serialized cron job for the frontend task list."""

    id: str
    name: str
    schedule: dict
    instruction: str
    enabled: bool
    delete_after_run: bool = False


@router.get(
    "/im/v1/agents/{agent_id}/cron/jobs",
    response_model=list[CronJobSummary],
    summary="List cron jobs for an agent",
)
def list_agent_cron_jobs(
    agent_id: str,
    service: ConfigService = Depends(get_config_service),
    user: User = Depends(current_user),
) -> list[CronJobSummary]:
    """Return all cron jobs registered for an agent.

    Jobs are read from <workspace_root>/.nanoassistant/cron/jobs.json.
    Returns an empty list when no jobs file exists yet.

    feat-394-M3 WARNING-3: spec Scenario "配置页查看并手动删除任务".
    """
    profile = service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    workspace_root = service.workspace_root_for_profile(profile)
    jobs_path = Path(workspace_root) / _CRON_JOBS_PATH
    if not jobs_path.exists():
        return []
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    result: list[CronJobSummary] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            result.append(CronJobSummary(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                schedule=item.get("schedule", {}),
                instruction=str(item.get("instruction", "")),
                enabled=bool(item.get("enabled", True)),
                delete_after_run=bool(item.get("delete_after_run", False)),
            ))
        except (TypeError, ValueError):
            continue
    return result


@router.delete(
    "/im/v1/agents/{agent_id}/cron/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a cron job for an agent",
)
def delete_agent_cron_job(
    agent_id: str,
    job_id: str,
    service: ConfigService = Depends(get_config_service),
    user: User = Depends(current_user),
) -> None:
    """Remove one cron job from the agent's jobs.json.

    feat-394-M3 WARNING-3: spec Scenario "配置页查看并手动删除任务".
    """
    profile = service.get_profile_for_owner(agent_id=agent_id, owner_id=user.owner_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_id not found")
    workspace_root = service.workspace_root_for_profile(profile)
    jobs_path = Path(workspace_root) / _CRON_JOBS_PATH
    if not jobs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_id not found")
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="could not read jobs") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="malformed jobs file")
    original_len = len(data)
    filtered = [item for item in data if isinstance(item, dict) and str(item.get("id", "")) != job_id]
    if len(filtered) == original_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_id not found")
    try:
        jobs_path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="could not write jobs") from exc
