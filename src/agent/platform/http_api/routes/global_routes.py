"""Global HTTP endpoints for health, capability discovery, and LLM config."""

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import __version__
from agent.core.errors import ModelError
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.model_registry import (
    get_default_model,
    list_provider_models,
    list_supported_providers,
)
from agent.platform.tools.registry import ToolRegistry

from ..auth import require_bearer_auth
from ..deps import APIError, get_agent_runtime, get_tool_registry

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
                "supports_text": metadata.supports_text,
                "supports_image": metadata.supports_image,
                "supports_tools": metadata.supports_tools,
                "supports_streaming": metadata.supports_streaming,
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
