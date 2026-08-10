"""Notice-route admission at the Gateway-to-Kernel submit boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionRequest,
    ForegroundTerminalSubscriptionOutcome,
)
from personal_assistant.gateway.inbound_models import InboundRunRequest
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:  # noqa: ANN001
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        message=message,
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


class _RouteRecordingSubscriptions:
    def __init__(self, operations: list[tuple[str, str]]) -> None:
        self.operations = operations
        self.routes: dict[str, ReplyContext] = {}

    def register_session_event_route(
        self, trace_id: str, reply_context: ReplyContext
    ) -> None:
        self.operations.append(("register", trace_id))
        self.routes[trace_id] = reply_context

    def discard_session_event_route(self, trace_id: str) -> None:
        self.operations.append(("discard", trace_id))
        self.routes.pop(trace_id, None)

    async def ensure_after_foreground_terminal(
        self, _request: BackgroundSubscriptionRequest
    ) -> ForegroundTerminalSubscriptionOutcome:
        return ForegroundTerminalSubscriptionOutcome.STARTED


@pytest.mark.asyncio
async def test_run_registers_exact_reply_route_before_submit(tmp_path: Path) -> None:
    """Admission freezes the current route before the same trace reaches Kernel."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    operations: list[tuple[str, str]] = []
    original_submit = kernel.submit

    def _recording_submit(**kwargs):  # noqa: ANN003, ANN202
        operations.append(("submit", str(kwargs.get("trace_id"))))
        return original_submit(**kwargs)

    kernel.submit = _recording_submit  # type: ignore[method-assign]
    subscriptions = _RouteRecordingSubscriptions(operations)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        background_subscriptions=subscriptions,  # type: ignore[arg-type]
    )
    message = inbound(chat_id="trace-route", text="work")
    running = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")

    trace_id = str(kernel.submit_calls[0]["trace_id"])
    assert trace_id
    assert operations[:2] == [("register", trace_id), ("submit", trace_id)]
    assert subscriptions.routes[trace_id].target_chat_id == "trace-route"

    kernel.finish("run-1", text="done")
    await running


@pytest.mark.asyncio
async def test_submit_failure_discards_registered_trace_route(tmp_path: Path) -> None:
    """A failed synchronous submit cannot leave an unowned route behind."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    operations: list[tuple[str, str]] = []
    subscriptions = _RouteRecordingSubscriptions(operations)

    def _fail_submit(**kwargs):  # noqa: ANN003, ANN202
        operations.append(("submit", str(kwargs.get("trace_id"))))
        raise RuntimeError("submit rejected")

    kernel.submit = _fail_submit  # type: ignore[method-assign]
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        background_subscriptions=subscriptions,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="submit rejected"):
        await coordinator.dispatch(
            _request(inbound(chat_id="submit-failure", text="work"), catalog)
        )

    assert [kind for kind, _ in operations] == ["register", "submit", "discard"]
    assert subscriptions.routes == {}
