from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from nano_multiagent import __version__
from nano_multiagent.llm.factory import LLMFactoryConfig
from nano_multiagent.llm.model_registry import (
    get_default_model,
    list_provider_models,
    list_supported_providers,
)
from nano_multiagent.tools.registry import ToolRegistry

from ..auth import require_bearer_auth
from ..deps import get_tool_registry

router = APIRouter()


@router.get("/v1/health")
def health() -> dict[str, bool | str]:
    return {
        "healthy": True,
        "version": __version__,
        "node_id": "local-dev",
    }


@router.get(
    "/v1/capabilities",
    dependencies=[Depends(require_bearer_auth)],
)
def capabilities(registry: ToolRegistry = Depends(get_tool_registry)) -> dict[str, Any]:
    return build_capabilities_payload(
        tool_registry=registry,
        llm_config=LLMFactoryConfig.from_env(),
    )


@router.get(
    "/v1/openapi.json",
    dependencies=[Depends(require_bearer_auth)],
)
def openapi_v1(request: Request) -> JSONResponse:
    return JSONResponse(content=request.app.openapi())


def build_capabilities_payload(
    *,
    tool_registry: ToolRegistry,
    llm_config: LLMFactoryConfig,
) -> dict[str, Any]:
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
        for spec in tool_registry.list_specs()
    ]

    return {
        "llm": {
            "active_provider": llm_config.provider,
            "active_model": llm_config.model,
            "providers": providers,
        },
        "tools": tools,
    }
