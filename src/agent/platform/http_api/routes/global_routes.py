"""Global HTTP endpoints for health, capability discovery, and LLM config."""

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import __version__
from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.errors import ModelError
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.model_registry import (
    get_default_model,
    list_provider_models,
    list_supported_providers,
)
from agent.platform.tools.registry import ToolRegistry

from ..auth import require_bearer_auth
from ..deps import APIError, get_agent_runtime, get_prompt_sections, get_tool_registry

router = APIRouter()


@router.get("/v1/health")
def health() -> dict[str, bool | str]:
    """Return liveness payload for probes and managed CLI startup checks."""
    return {
        "healthy": True,
        "version": __version__,
        "node_id": "local-dev",
    }


@router.get(
    "/v1/capabilities",
    dependencies=[Depends(require_bearer_auth)],
)
def capabilities(
    registry: ToolRegistry = Depends(get_tool_registry),
    runtime=Depends(get_agent_runtime),
) -> dict[str, Any]:
    """Describe current LLM/tool capabilities exposed by this HTTP node."""
    return build_capabilities_payload(
        tool_registry=registry,
        llm_config=runtime.get_llm_config(),
    )


class LLMConfigResponse(BaseModel):
    """Response schema for current runtime LLM configuration."""

    provider: str
    model: str
    base_url: str
    api_key: str | None = None
    timeout_seconds: float


class PatchLLMConfigRequest(BaseModel):
    """Partial update request schema for LLM runtime configuration."""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    clear_api_key: bool | None = None


@router.get(
    "/v1/llm-config",
    response_model=LLMConfigResponse,
    dependencies=[Depends(require_bearer_auth)],
)
def get_llm_config(runtime=Depends(get_agent_runtime)) -> LLMConfigResponse:
    """Fetch current runtime LLM config via HTTP boundary."""
    return _to_llm_config_response(runtime.get_llm_config())


@router.patch(
    "/v1/llm-config",
    response_model=LLMConfigResponse,
    dependencies=[Depends(require_bearer_auth)],
)
def patch_llm_config(
    payload: PatchLLMConfigRequest,
    runtime=Depends(get_agent_runtime),
) -> LLMConfigResponse:
    """Patch runtime LLM config and map runtime/provider errors to HTTP codes."""
    fields_set = payload.model_fields_set
    _ensure_patch_request_is_valid(payload=payload, fields_set=fields_set)

    update_api_key = "api_key" in fields_set or payload.clear_api_key is True
    provider = _require_non_null_if_provided("provider", payload.provider, fields_set)
    model = _require_non_null_if_provided("model", payload.model, fields_set)
    base_url = _require_non_null_if_provided("base_url", payload.base_url, fields_set)
    timeout_seconds = _require_non_null_if_provided(
        "timeout_seconds",
        payload.timeout_seconds,
        fields_set,
    )
    api_key = payload.api_key
    if payload.clear_api_key:
        api_key = None

    try:
        config = runtime.reconfigure_llm(
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
            update_api_key=update_api_key,
        )
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    except ModelError as exc:
        raise APIError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        ) from exc
    return _to_llm_config_response(config)


@router.get(
    "/v1/openapi.json",
    dependencies=[Depends(require_bearer_auth)],
)
def openapi_v1(request: Request) -> JSONResponse:
    """Return OpenAPI schema document under authenticated `/v1` namespace."""
    return JSONResponse(content=request.app.openapi())


def build_capabilities_payload(
    *,
    tool_registry: ToolRegistry,
    llm_config: LLMFactoryConfig,
) -> dict[str, Any]:
    """Build capabilities payload consumed by CLI/SDK feature discovery."""
    providers: list[dict[str, Any]] = []
    for provider in list_supported_providers():
        models = [
            {
                "model": metadata.model,
                "default_base_url": metadata.default_base_url,
            }
            for metadata in list_provider_models(provider)
        ]
        providers.append(
            {
                "provider": provider,
                "default_model": get_default_model(provider),
                "models": models,
            }
        )

    tools = [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": dict(spec.input_schema),
        }
        for spec in sorted(tool_registry.list_specs(), key=lambda spec: spec.name)
    ]

    return {
        "llm": {
            "active_provider": llm_config.provider,
            "active_model": llm_config.model,
            "providers": providers,
        },
        "tools": tools,
    }


def _to_llm_config_response(config: LLMFactoryConfig) -> LLMConfigResponse:
    """Convert runtime config model into HTTP response schema."""
    return LLMConfigResponse(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )


def _require_non_null_if_provided(
    field_name: str,
    value: Any,
    fields_set: set[str],
) -> Any:
    """Reject explicit null on fields that must be concrete when present."""
    if field_name not in fields_set:
        return None
    if value is None:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=f"'{field_name}' cannot be null",
            retryable=False,
        )
    return value


def _ensure_patch_request_is_valid(
    *,
    payload: PatchLLMConfigRequest,
    fields_set: set[str],
) -> None:
    """Enforce mutually exclusive patch semantics before runtime reconfigure."""
    if not fields_set:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message="at least one llm config field is required",
            retryable=False,
        )
    if payload.clear_api_key is False and fields_set == {"clear_api_key"}:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message="at least one llm config field is required",
            retryable=False,
        )
    if "clear_api_key" in fields_set and payload.clear_api_key is None:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message="'clear_api_key' cannot be null",
            retryable=False,
        )
    if payload.clear_api_key and "api_key" in fields_set and payload.api_key is not None:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message="'api_key' cannot be set when 'clear_api_key' is true",
            retryable=False,
        )


# ---------------------------------------------------------------------------
# Prompt preview (feat-379-M2 R5)
# ---------------------------------------------------------------------------


class PromptPreviewRequest(BaseModel):
    """Request body for the prompt preview endpoint.

    Args:
        features: Per-agent feature flags (key → bool).  Absent key defaults
            to the FEATURE_REGISTRY default_on value.  Passed to PromptContext.flags.
        custom_prompt: Optional user-supplied text appended as a supplement
            segment.  Passed to PromptContext.vars["custom_prompt"].
        tool_ids: Tool names to mark as active for this preview turn (determines
            which tool-gated sections are included).
        scenario: Conversation type hint ("direct" or "group").  Defaults to
            "direct" so previews omit group-only segments.
        workspace_root: Absolute workspace path for this agent.  Used as ctx.cwd
            and as the root for skill discovery.  When absent, cwd falls back to
            a placeholder indicating the value will be injected at runtime.
        skill_ids: Skill names to resolve from workspace_root and include in
            ctx.available_skills.  Unknown names are silently skipped.
    """

    features: dict[str, bool] = Field(default_factory=dict)
    custom_prompt: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    scenario: str = "direct"
    workspace_root: str | None = None
    skill_ids: list[str] = Field(default_factory=list)


class PromptPreviewResponse(BaseModel):
    """Assembled system-prompt preview string (cache-stable segments only)."""

    prompt: str
    section_count: int


@router.post(
    "/v1/prompt-preview",
    response_model=PromptPreviewResponse,
    dependencies=[Depends(require_bearer_auth)],
)
def prompt_preview(
    payload: PromptPreviewRequest,
    sections: list = Depends(get_prompt_sections),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> PromptPreviewResponse:
    """Assemble a system-prompt preview for the given per-agent feature configuration.

    Volatile segments (cache_safe=False — memory_block, user_profile_block,
    communication_context, etc.) appear inline at their natural order position as
    readable '运行时注入' placeholders.  This preserves the complete prompt shape so
    the preview reads as a coherent document and the user sees exactly where runtime
    will inject content — same principle as the datetime placeholder.

    feat-383-M1: tool descriptions come from the real ToolRegistry; skills are
    resolved from workspace_root; datetime uses a placeholder to signal runtime
    injection; cwd uses workspace_root or a placeholder when not available.

    feat-385-M3-fix-r2 P1: volatile segments appear inline (not stripped then
    footer-stacked).  _make_volatile_placeholder_section converts each
    cache_safe=False section into an always-enabled section whose render returns
    a human-readable inline placeholder text describing what runtime injects.

    Args:
        payload: Feature flags, custom_prompt, active tool ids, workspace_root,
            skill_ids, and scenario hint.
        sections: PromptSection list from app.state (populated by bootstrap).
        registry: ToolRegistry from app.state for real tool description lookup.

    Returns:
        PromptPreviewResponse with the assembled prompt and section count.
    """
    from pathlib import Path  # noqa: PLC0415

    from agent.core.agent.prompt_sections.base import RenderMode  # noqa: PLC0415
    from agent.core.skills.discovery import resolve_available_skills  # noqa: PLC0415

    # Use real tool objects from registry; silently skip ids not registered
    # (mirrors runtime behaviour — unregistered tools are never exposed to agent).
    available_tools = tuple(
        t for t in (registry.get(tid) for tid in payload.tool_ids) if t is not None
    )

    # Resolve skills from workspace when available; empty when workspace unknown.
    # skill_ids is always an explicit list (default_factory=list), so we treat
    # it as the exact include set — never falls through to "load all skills".
    if payload.workspace_root:
        available_skills = resolve_available_skills(
            workspace_root=Path(payload.workspace_root),
            include_names=payload.skill_ids,
        )
    else:
        available_skills = ()

    # datetime is runtime-volatile; show placeholder so users see the field exists
    # but understand it will be filled at runtime (spec Q3 / decision 4).
    current_datetime = "<运行时注入：当前时间>"

    # cwd is known when workspace_root is provided; otherwise show placeholder.
    cwd = payload.workspace_root if payload.workspace_root else "<运行时注入：workspace 路径>"

    # M4 Decision 19: preview uses render_mode=PREVIEW so volatile segments render
    # their banner + '运行时注入' placeholder via core segment logic — no platform hack
    # needed.  The former _make_volatile_placeholder_section is deleted; core segments
    # handle all three states (PREVIEW / RUNTIME+data / RUNTIME+no-data) internally.
    ctx = PromptContext(
        available_tools=available_tools,
        available_skills=available_skills,
        current_datetime=current_datetime,
        cwd=cwd,
        # memory_content / user_profile_content left as None — segments use
        # render_mode=PREVIEW to generate banner + inline placeholder.
        render_mode=RenderMode.PREVIEW,
        flags=payload.features,
        scenario={"conversation_type": payload.scenario},
        vars={"custom_prompt": payload.custom_prompt} if payload.custom_prompt else {},
    )

    # Count stable sections for the response; all sections pass through unchanged —
    # volatile segments render their own placeholder via render_mode (Decision 19).
    stable_count = sum(1 for sec in sections if getattr(sec, "cache_safe", True))
    assembled = assemble_system_prompt(sections, ctx)
    return PromptPreviewResponse(prompt=assembled, section_count=stable_count)
