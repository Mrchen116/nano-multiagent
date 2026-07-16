"""Run-identity guarantees for SessionRunCoordinator steer admission."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.gateway.inbound_models import InboundRunRequest
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        message=message,
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


@pytest.mark.asyncio
async def test_replaced_kernel_run_gets_no_follower_and_falls_back_once(
    tmp_path: Path,
) -> None:
    """A coordinator marker for A cannot steer or register a follower on B."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first_message = inbound(chat_id="chat-a", text="first")
    first = asyncio.create_task(coordinator.dispatch(_request(first_message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    kernel.forced_active_run_id = "replacement-run-b"

    follower = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="chat-a", text="follower"), catalog)
        )
    )
    await kernel.wait_try_steer_count(1)

    assert kernel.try_steer_calls[-1]["expected_run_id"] == "run-1"
    assert not follower.done()
    kernel.finish("run-1", text="first done")
    assert (await first).run_id == "run-1"
    kernel.forced_active_run_id = None
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="fallback done")

    result = await follower
    assert result.run_id == "run-2"
    assert [call["run_id"] for call in kernel.submit_calls if not call["steer"]] == [
        "run-1",
        "run-2",
    ]
