"""Product-owned publication callbacks bound to an active kernel run."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class OutputCandidate:
    """One model generation's complete text before publication."""

    session_id: str
    run_id: str | None
    candidate_id: str
    context_revision: int
    text: str
    message_ids: tuple[str, ...]
    turn_id: str | None = None
    group_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PermissionOutcome:
    """Permission decision without executing a model tool call."""

    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class OutputResult:
    """Actual publication state returned by the product delivery owner."""

    state: Literal["pass_through", "delivered", "withheld", "pending", "partial"] = (
        "pass_through"
    )
    reason_code: str | None = None
    diagnostic: str | None = None
    continuation: str | None = None
    delivery_id: str | None = None
    channel_receipts: tuple[Mapping[str, Any], ...] = ()


class OutputControl(Protocol):
    """Run-scoped permission and atomic publication admission."""

    async def authorize_tool(
        self, name: str, arguments: Mapping[str, Any]
    ) -> PermissionOutcome:
        """Evaluate the registered tool's permission chain without executing it."""
        ...

    def try_commit(
        self, enqueue: Callable[[], None]
    ) -> Literal["committed", "stale", "inactive"]:
        """Atomically admit an enqueue against the candidate's run revision."""
        ...


class OutputHandler(Protocol):
    """Consumer callback for one complete model text candidate."""

    async def __call__(
        self, candidate: OutputCandidate, control: OutputControl
    ) -> OutputResult:
        """Resolve publication and return its actual delivery state."""
        ...


class _OutputControlAdapter:
    def __init__(self, control: Any) -> None:
        self._control = control

    async def authorize_tool(
        self, name: str, arguments: Mapping[str, Any]
    ) -> PermissionOutcome:
        payload = await self._control.authorize_tool(name, arguments)
        return PermissionOutcome(
            allowed=not bool(payload.get("block")), reason=payload.get("reason")
        )

    def try_commit(self, enqueue: Callable[[], None]) -> str:
        return self._control.try_commit(enqueue)


def adapt_output_handler(handler: OutputHandler):
    """Adapt SDK-owned records to the core's structural callback boundary."""

    async def invoke(candidate, control):
        return await handler(
            OutputCandidate(**candidate), _OutputControlAdapter(control)
        )

    return invoke
