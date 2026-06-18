"""bugfix-417-M5 (#114): a user /stop attaches the CC-identical user-attribution
content to the terminal reconcile so the in-flight tool card shows the same body the
model reads in the transcript. System reaps (watchdog/crash) carry no content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdk import USER_INTERRUPT_RECOVERY_CONTENT
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel


def _build_pipeline(observer: Any) -> InboundPipeline:
    return InboundPipeline(
        kernel=object(),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a", workspace_root=Path("/tmp"), title="Agent A"
            ),
        ),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        kernel_event_observer=observer,
    )


def test_reconcile_carries_user_content_for_user_interrupted_run() -> None:
    """A run marked user-interrupted yields a reconcile event with the CC content +
    finalize_bubble. bugfix-417-fix2: the membership signal is NOT consumed by the
    reconcile (it persists until the per-run `finally` chokepoint), so the race-free
    direct reconcile from _handle_stop_command AND a later stream-driven reconcile both
    see the user-stop attribution; the reconcile itself is idempotent."""
    seen: list[dict] = []
    pipeline = _build_pipeline(lambda ev: seen.append(dict(ev)))

    pipeline._user_interrupted_runs.add("run-stop")
    pipeline._emit_terminal_reconcile("run-stop", reason="interrupted")

    assert len(seen) == 1
    assert seen[0]["reason"] == "interrupted"
    assert seen[0]["content"] == USER_INTERRUPT_RECOVERY_CONTENT
    assert seen[0]["finalize_bubble"] is True
    # NOT consumed here — discarded once in the per-run finally; a second reconcile
    # still carries the attribution (idempotent at the observer via popped tool calls).
    assert "run-stop" in pipeline._user_interrupted_runs
    pipeline._emit_terminal_reconcile("run-stop", reason="interrupted")
    assert seen[1]["content"] == USER_INTERRUPT_RECOVERY_CONTENT


def test_reconcile_omits_content_for_system_reap() -> None:
    """A run NOT user-interrupted (watchdog/crash) yields no content attribution."""
    seen: list[dict] = []
    pipeline = _build_pipeline(lambda ev: seen.append(dict(ev)))

    pipeline._emit_terminal_reconcile("run-watchdog", reason="stalled")

    assert len(seen) == 1
    assert seen[0]["reason"] == "stalled"
    assert "content" not in seen[0]
