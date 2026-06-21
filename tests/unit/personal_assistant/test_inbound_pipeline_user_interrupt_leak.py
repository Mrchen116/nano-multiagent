"""bugfix-417-fix1 (B): _user_interrupted_runs must not leak.

A user /stop marks the active run_id in _user_interrupted_runs so the terminal
reconcile can attribute the in-flight tool card content to the user. The marker is
discarded when the reconcile fires — but a run that reaches a terminal state WITHOUT
a reconcile (watchdog reap / crash / normal completion of a non-/stop run) would
otherwise leak the entry forever. The per-run `finally` chokepoint (where
_active_runs is popped) is the guaranteed terminal path, so the marker is cleared
there too.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel, _FakeKernel


def _build(tmp_path: Path) -> tuple[InboundPipeline, _FakeKernel]:
    agent_dir = tmp_path / "agent-a"
    agent_dir.mkdir()
    kernel = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a", workspace_root=agent_dir, title="Agent A"
            ),
        ),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    return pipeline, kernel


def test_user_interrupt_marker_cleared_on_terminal_without_reconcile(
    tmp_path: Path,
) -> None:
    """A marked run that completes via its `_run` finally (no reconcile fired) must
    have its _user_interrupted_runs entry discarded — bounding the set."""
    pipeline, kernel = _build(tmp_path)

    # The first run submitted by _FakeKernel gets run_id "run-1". Pre-mark it as if a
    # prior /stop had targeted it; this run then completes normally (no reconcile on
    # the happy path), so only the `finally` chokepoint can clear the marker.
    pipeline._user_interrupted_runs.add("run-1")

    inbound = InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert kernel.send_calls and kernel.send_calls[0]["run_id"] == "run-1"
    # The run reached a terminal state and the per-run finally discarded the marker.
    assert "run-1" not in pipeline._user_interrupted_runs, (
        "user-interrupt marker leaked: run reached terminal without clearing it"
    )
