"""bugfix-426-M4 (#140): a steer consumed at the run's collapse window keeps its
reply on the SAME run and rolls the IM bubble — events are not dropped, no timeout.

#140 reproduction: a steer landed in the run's terminal window → was stranded → the
registry re-ran it as a continuation with a NEW run_id → the gateway relay
(``_await_terminal_run_async``, anchored to the old run_id) dropped every continuation
event via ``if event.get("run_id") != run_id: continue`` → the IM placeholder bubble
got no events for 120s → watchdog failed it → 6 分钟黑屏.

This drives the REAL inbound pipeline relay (``_await_terminal_run_async``) and the REAL
observer over a scripted kernel stream that mirrors the fixed kernel: the steer's reply
events carry the SAME run_id (决策5), with an ``injection_consumed`` signal at the
consume point (决策6). The test asserts:

- the post-steer events are surfaced (not dropped) — the relay stays anchored to the
  one run, so the reply streams through;
- the observer rolls the bubble: bubble A is finalized ``completed`` (not failed — the
  #140 watchdog symptom) and a new bubble B opens at the consume point, with the
  steer's reply streaming into B;
- the run reaches a clean terminal (completed) — no relay-idle timeout / black screen.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.main import _build_kernel_event_observer

from ._pipeline_helpers import _FakeChannel, _FakeSseKernel, _agents


class _FakeIMManager:
    """Capture node.streaming_delta frames; answer turn_start acks with fresh ids."""

    connected = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._bubble_seq = 0

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.sent.append((message_type, payload))

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.sent.append((message_type, payload))
        self._bubble_seq += 1
        return {"payload": {"message_id": f"bubble-{self._bubble_seq}"}}

    def deltas(self) -> list[dict[str, Any]]:
        return [p for mt, p in self.sent if mt == "node.streaming_delta"]


def test_collapse_window_steer_streams_reply_in_new_bubble_no_timeout(
    tmp_path: Path,
) -> None:
    # Pre-seed the run context the way the relay-lifecycle "accepted" phase does
    # (conversation/agent meta, empty message_id filled by the turn_start ack). The
    # lifecycle seeding itself is covered by test_inbound_pipeline_streaming; here we
    # exercise the observer's stream handling + relay anchoring.
    run_context_store: dict[str, dict[str, str]] = {
        "run-1": {"conversation_id": "chat-1", "message_id": "", "agent_id": "agent-a"}
    }
    manager = _FakeIMManager()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
        running_tool_calls={},
    )

    # Scripted stream mirroring the FIXED kernel: one run (run-1) throughout — the
    # prior reply, then the steer consume signal, then the steer's own tool work and
    # reply, all on run-1 (决策5 keeps the run; before #140 these were a new run_id
    # and the relay dropped them).
    kernel = _FakeSseKernel(
        events=[
            {"event": "run_status", "run_id": "run-1", "status": "running"},
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kmsg-A",
                "content": "working on the original ask",
            },
            # Collapse window: the user steered; the loop consumed it on the SAME run
            # and signalled the consume point. The bubble切点 is HERE — before the
            # steer's first output — so the steer's tool work belongs to the NEW bubble
            # B, not appended to A. (Without the injection_consumed roll, these tool
            # cards would attach to bubble A because the kernel emits no assistant text
            # before them — _close_old_and_restart only fires on assistant_message.)
            {"event": "injection_consumed", "run_id": "run-1", "turn_id": "turn-1"},
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-steer",
                "name": "web_search",
                "arguments": {"query": "new request"},
            },
            {
                "event": "tool_end",
                "run_id": "run-1",
                "call_id": "call-steer",
                "name": "web_search",
                "duration_ms": 7,
            },
            # The steer's reply — these are the events #140 used to drop.
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kmsg-B",
                "content": "ok, switching to your new request",
            },
            {"event": "run_status", "run_id": "run-1", "status": "completed"},
        ]
    )
    # Mark run-1 active so the (separate) steer submit injects rather than creating a
    # second run — but this test exercises the RELAY stream, so the active map only
    # needs to keep the first run's stream anchored.
    kernel.run_states["run-1"] = {"run_id": "run-1", "status": "completed"}

    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=_agents(tmp_path),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        kernel_event_observer=observer,
    )

    inbound = InboundMessage(
        channel_name="web_relay",
        text="do the original ask",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    # The run reached a clean terminal — no relay-idle timeout was raised (a dropped
    # stream would have ended without terminal run_status and raised RuntimeError).
    assert result is not None

    kinds = [d.get("kind") for d in manager.deltas()]
    # Bubble A opened (turn_start), streamed the original reply, then on the steer
    # consume point: A finalized completed, B opened, B streamed the steer reply.
    assert "turn_start" in kinds
    assert "message_completed" in kinds

    # Bubble A was finalized as COMPLETED (clean), not failed (the #140 symptom).
    a_completed = [
        d
        for d in manager.deltas()
        if d.get("kind") == "message_completed"
        and d.get("delivery_status") == "completed"
    ]
    assert a_completed, "bubble A must finalize completed, not failed/timeout"

    # The steer reply (post-consume) was surfaced — not dropped — and streamed into a
    # bubble opened AFTER the consume point (two turn_starts: A then B).
    turn_starts = [d for d in manager.deltas() if d.get("kind") == "turn_start"]
    assert len(turn_starts) >= 2, "a new bubble B must open at the steer consume point"
    steer_deltas = [
        d
        for d in manager.deltas()
        if d.get("kind") == "message_delta"
        and "switching to your new request" in str(d.get("delta_text") or "")
    ]
    assert steer_deltas, "the steer's reply must stream through (not be dropped)"

    # Decision-6 core: the consume signal rolls the bubble BEFORE the steer's first
    # output, so the steer's tool card attaches to the NEW bubble B — not bubble A
    # (which was answering the prior message). The message_completed for A is sent
    # before B opens, so the steer tool_call_upserted must carry a message_id that is
    # NOT the one A finalized.
    a_finalized_ids = {
        str(d.get("message_id"))
        for d in manager.deltas()
        if d.get("kind") == "message_completed"
        and d.get("delivery_status") == "completed"
    }
    steer_tool_frames = [
        d
        for d in manager.deltas()
        if d.get("kind") == "tool_call_upserted"
        and isinstance(d.get("tool_call"), dict)
        and d["tool_call"].get("id") == "call-steer"
    ]
    assert steer_tool_frames, "the steer's tool work must be surfaced"
    assert all(
        str(d.get("message_id")) not in a_finalized_ids for d in steer_tool_frames
    ), "the steer's tool card must attach to bubble B, not the finalized bubble A"
