from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from nano_multiagent.tools.registry import ToolRegistry

from ..auth import require_bearer_auth
from ..deps import get_tool_registry

router = APIRouter(
    prefix="/v1/tools",
    tags=["tools"],
    dependencies=[Depends(require_bearer_auth)],
)


class ToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolListResponse(BaseModel):
    tools: list[ToolDescriptor]


@router.get("", response_model=ToolListResponse)
def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> ToolListResponse:
    tools = [
        ToolDescriptor(
            name=spec.name,
            description=spec.description,
            input_schema=dict(spec.input_schema),
        )
        for spec in registry.list_specs()
    ]
    return ToolListResponse(tools=tools)
