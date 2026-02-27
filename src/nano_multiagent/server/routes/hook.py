from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.types import ALL_HOOK_EVENTS, HookRegistration, event_mode_of

from ..auth import require_bearer_auth
from ..deps import get_hook_registry

router = APIRouter(
    prefix="/v1/hooks",
    tags=["hooks"],
    dependencies=[Depends(require_bearer_auth)],
)

HookMode = Literal["observe", "intercept"]

_RETURN_CONTRACTS: dict[str, str] = {
    "input": "action=continue|transform|handled; transform may include text/images",
    "before_agent_start": "optional message/system_prompt override",
    "tool_call": "optional block=true with reason",
    "tool_result": "optional output/content/details/is_error/error rewrite",
}


class HookEventDescriptor(BaseModel):
    event: str
    mode: HookMode
    return_contract: str


class HookEventListResponse(BaseModel):
    events: list[HookEventDescriptor]


class HookDescriptor(BaseModel):
    hook_id: str
    event: str
    mode: HookMode
    source: str
    module_name: str | None = None
    file_path: str | None = None
    priority: int
    timeout_ms: int


class HookListResponse(BaseModel):
    hooks: list[HookDescriptor]


@router.get("/events", response_model=HookEventListResponse)
def list_hook_events() -> HookEventListResponse:
    return HookEventListResponse(events=build_event_descriptors())


@router.get("", response_model=HookListResponse)
def list_hooks(registry: HookRegistry = Depends(get_hook_registry)) -> HookListResponse:
    return HookListResponse(hooks=build_hook_descriptors(registry))


def build_event_descriptors() -> list[HookEventDescriptor]:
    return [
        HookEventDescriptor(
            event=event_name,
            mode=event_mode_of(event_name).value,
            return_contract=_return_contract(event_name),
        )
        for event_name in sorted(ALL_HOOK_EVENTS)
    ]


def build_hook_descriptors(registry: HookRegistry) -> list[HookDescriptor]:
    return [_to_hook_descriptor(item) for item in registry.all_handlers()]


def _to_hook_descriptor(registration: HookRegistration) -> HookDescriptor:
    return HookDescriptor(
        hook_id=registration.hook_id,
        event=registration.event,
        mode=event_mode_of(registration.event).value,
        source=registration.source,
        module_name=registration.module_name,
        file_path=str(registration.file_path) if registration.file_path is not None else None,
        priority=registration.priority,
        timeout_ms=registration.timeout_ms,
    )


def _return_contract(event_name: str) -> str:
    return _RETURN_CONTRACTS.get(event_name, "none")
