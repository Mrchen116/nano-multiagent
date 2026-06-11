"""Inbound pipeline SSE path tests (feat-338 cutover) and map_kernel_event mapping."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel, _FakeSseKernel, _agents


def test_inbound_pipeline_uses_sse_path_when_submit_and_stream_available(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-1", "content": "sse reply"},
            {"event": "run_status", "run_id": "run-1", "status": "completed"},
        ]
    )
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="ping",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.agent_id == "agent-a"
    assert result.reply_text == "sse reply"
    # M3: kernel.submit replaces submit_message; priority is not exposed on the SDK interface.
    assert len(kernel_client.submit_calls) == 1
    assert kernel_client.submit_calls[0]["session_id"] == "sess-1"
    assert kernel_client.submit_calls[0]["texts"] == ["ping"]
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="sse reply",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]


def test_inbound_pipeline_sse_path_extracts_reply_from_assistant_message(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "tool_start", "run_id": "run-1", "tool_name": "web_search"},
            {"event": "assistant_message", "run_id": "run-1", "content": "found it"},
            {"event": "tool_end", "run_id": "run-1", "tool_name": "web_search"},
            {"event": "run_status", "run_id": "run-1", "status": "completed"},
        ]
    )
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="search",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "found it"


def test_inbound_pipeline_sse_path_raises_on_failed_run(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-1", "content": "oops"},
            {
                "event": "run_status",
                "run_id": "run-1",
                "status": "failed",
                "error": "boom",
            },
        ]
    )
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="fail",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    try:
        asyncio.run(pipeline.handle_inbound(inbound))
        raise AssertionError("expected exception")
    except Exception as exc:
        assert "boom" in str(exc)


def test_inbound_pipeline_sse_path_routes_non_user_origin_events(
    tmp_path: Path,
) -> None:
    """Events with origin != user and mismatched run_id are routed outbound.

    This verifies the session_key serial queue handles background-wake / cron
    events while the user run is in progress.
    """
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {
                "event": "assistant_message",
                "run_id": "run-other",
                "content": "background",
                "origin": "background_task",
            },
            {"event": "assistant_message", "run_id": "run-1", "content": "user reply"},
            {"event": "run_status", "run_id": "run-1", "status": "completed"},
        ]
    )
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="ping",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "user reply"
    assert "background" in [msg.text for msg in channel.sent]


def test_inbound_pipeline_sse_path_relay_lifecycle_emits_completed_with_usage(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-1", "content": "ok"},
            {
                "event": "run_status",
                "run_id": "run-1",
                "status": "completed",
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        ]
    )
    seen: list = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        del message
        seen.append(update)

    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        relay_lifecycle_callback=_capture,
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="ping",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    phases = [u.phase for u in seen]
    assert phases == ["accepted", "running", "completed"]
    assert seen[-1].usage == {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }


def test_idle_run_is_cancelled_and_next_same_session_message_continues(
    tmp_path: Path,
) -> None:
    """A silent kernel run must not permanently block the session FIFO."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))

    class _IdleThenSuccessfulKernel(_FakeSseKernel):
        def __init__(self) -> None:
            super().__init__(events=[])
            self.cancelled_run_ids: list[str] = []

        def cancel(self, run_id: str):  # noqa: ANN201
            self.cancelled_run_ids.append(run_id)
            return None

        def stream(self, session_id: str, *, after_sequence: int = 0):  # noqa: ANN201
            del session_id, after_sequence
            run_id = self.send_calls[-1]["run_id"]

            async def _gen():  # noqa: ANN202
                yield {
                    "event": "run_status",
                    "run_id": run_id,
                    "status": "running",
                }
                if run_id == "run-1":
                    await asyncio.Event().wait()
                yield {
                    "event": "assistant_message",
                    "run_id": run_id,
                    "content": "second reply",
                }
                yield {
                    "event": "run_status",
                    "run_id": run_id,
                    "status": "completed",
                }

            return _gen()

    kernel = _IdleThenSuccessfulKernel()
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        run_idle_timeout_seconds=0.01,
    )
    first = InboundMessage(
        channel_name="web_relay",
        text="first",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
    )
    second = InboundMessage(
        channel_name="web_relay",
        text="second",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
    )

    async def _exercise() -> tuple[BaseException | None, object]:
        first_task = asyncio.create_task(pipeline.handle_inbound(first))
        await asyncio.sleep(0)
        second_task = asyncio.create_task(pipeline.handle_inbound(second))
        first_result, second_result = await asyncio.gather(
            first_task, second_task, return_exceptions=True
        )
        return (
            first_result if isinstance(first_result, BaseException) else None,
            second_result,
        )

    first_error, second_result = asyncio.run(_exercise())

    assert isinstance(first_error, TimeoutError)
    assert kernel.cancelled_run_ids == ["run-1"]
    assert second_result is not None
    assert second_result.reply_text == "second reply"
    assert channel.sent[-1].text == "second reply"


def test_map_kernel_event_to_run_activity() -> None:
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    assert (
        InboundPipeline._map_kernel_event_to_run_activity(
            {"event": "run_status", "status": "running"}
        )
        == "agent.run.started"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity(
            {"event": "run_status", "status": "completed"}
        )
        == "agent.run.completed"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity(
            {"event": "run_status", "status": "failed"}
        )
        == "agent.run.failed"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity(
            {"event": "run_status", "status": "cancelled"}
        )
        == "agent.run.failed"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity(
            {"event": "assistant_message"}
        )
        == "agent.text.message"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity({"event": "tool_start"})
        == "agent.tool.started"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity({"event": "tool_end"})
        == "agent.tool.completed"
    )
    assert (
        InboundPipeline._map_kernel_event_to_run_activity({"event": "turn_end"}) is None
    )
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "error"}) is None


# ---------------------------------------------------------------------------
# refactor-387 M3: workspace_root is no longer forwarded to stream() — in-process mode
# resolves session JSONL at create_session time via the agent workspace configuration.
# ---------------------------------------------------------------------------


def test_inbound_pipeline_stream_called_with_session_id(tmp_path: Path) -> None:
    """_await_terminal_run_async must call kernel.stream(session_id, ...).

    refactor-387 M3: workspace_root is not passed to stream() — the in-process
    Kernel already knows where session data lives (set at create_session time).
    """
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")

    stream_calls: list[dict] = []

    class _TrackingFakeSseKernel(_FakeSseKernel):
        def stream(self, session_id: str, *, after_sequence: int = 0):  # type: ignore[override]
            stream_calls.append(
                {"session_id": session_id, "after_sequence": after_sequence}
            )
            preset = [
                {"event": "assistant_message", "run_id": "run-1", "content": "ok"},
                {"event": "run_status", "run_id": "run-1", "status": "completed"},
            ]

            async def _gen():
                for event in preset:
                    yield dict(event)

            return _gen()

    kernel_client = _TrackingFakeSseKernel()
    from personal_assistant.gateway.channel_registry import ChannelRegistry
    from personal_assistant.gateway.outbound_router import OutboundRouter
    from personal_assistant.gateway.run_queue import SessionRunQueue
    from personal_assistant.gateway.session_keys import SessionBindingStore

    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert stream_calls, "kernel.stream() must have been called"
    assert stream_calls[0]["session_id"] == "sess-1"


# ---------------------------------------------------------------------------
# bugfix-404-M3: pipeline must relay BACKGROUND_TASK run output to IM channel
# (See test_background_session_events.py for the subscriber-level relay tests)
# ---------------------------------------------------------------------------


def test_ensure_background_subscriber_wires_bg_run_output_callback(
    tmp_path: Path,
) -> None:
    """_ensure_background_subscriber wires bg_run_output_callback when both reply_context
    and _bg_reply_sender are set.

    This tests the integration between InboundPipeline._ensure_background_subscriber
    and BackgroundSessionEventSubscriber: after a main turn completes, when the pipeline
    has both reply_context and a _bg_reply_sender wired, the subscriber must be created
    with a non-None bg_run_output_callback (bugfix-404-M3).

    When _bg_reply_sender is absent (pre-M3 or misconfigured gateway), the callback must
    be None — WebRelayAdapter.sent.append() is a no-op that never reaches IM.
    """
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    kernel = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-1", "content": "ok", "origin": "user"},
            {"event": "run_status", "run_id": "run-1", "status": "completed", "origin": "user"},
        ]
    )

    # Case 1: no _bg_reply_sender → bg_run_output_callback must be None
    pipeline_no_sender = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="web",
        text="hi",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    asyncio.run(pipeline_no_sender.handle_inbound(inbound))
    if pipeline_no_sender._bg_subscribers:
        sub_no_sender = list(pipeline_no_sender._bg_subscribers.values())[0]
        assert sub_no_sender._bg_run_output_callback is None, (
            "Without _bg_reply_sender, bg_run_output_callback must be None "
            "(outbound_router.send_text → WebRelayAdapter.sent.append is a no-op)"
        )
        asyncio.run(sub_no_sender.stop())

    # Case 2: _bg_reply_sender is wired → bg_run_output_callback must be non-None
    sent_texts: list[str] = []

    async def _fake_bg_reply_sender(text: str, reply_context: Any, from_session_id: str) -> None:
        sent_texts.append(text)

    pipeline_with_sender = InboundPipeline(
        kernel=_FakeSseKernel(
            events=[
                {"event": "assistant_message", "run_id": "run-1", "content": "ok", "origin": "user"},
                {"event": "run_status", "run_id": "run-1", "status": "completed", "origin": "user"},
            ]
        ),
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    pipeline_with_sender._bg_reply_sender = _fake_bg_reply_sender  # type: ignore[assignment]

    inbound2 = InboundMessage(
        channel_name="web",
        text="hi2",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    asyncio.run(pipeline_with_sender.handle_inbound(inbound2))
    assert pipeline_with_sender._bg_subscribers, "background subscriber must be created"
    sub_with_sender = list(pipeline_with_sender._bg_subscribers.values())[0]
    assert sub_with_sender._bg_run_output_callback is not None, (
        "With _bg_reply_sender wired, bg_run_output_callback must be non-None "
        "so BACKGROUND_TASK run output can be relayed to IM (bugfix-404-M3)"
    )
    asyncio.run(sub_with_sender.stop())


@pytest.mark.asyncio
async def test_bg_relay_callback_carries_idempotency_key(tmp_path: Path) -> None:
    """bg_run_output_callback must pass a from_session_id with |tool_call: suffix.

    bugfix-404 F1: without a stable idempotency key in from_session_id, IM has no
    dispatch_request_key and cannot deduplicate replayed BACKGROUND_TASK replies
    after a gateway restart.  The relay closure must encode
    ``<agent_id>|tool_call:<kernel_session_id>:<seq>`` as the from_session_id so
    IM's _handle_agent_message dedup path is engaged.

    Regression (修前红): before F1, from_session_id was bare ``<agent_id>`` with no
    ``|tool_call:`` suffix → dispatch_request_key was None → dedup skipped → same
    message duplicated in IM on replay.
    """
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    captured: list[str] = []

    async def _sender(text: str, reply_context: Any, from_session_id: str) -> None:
        captured.append(from_session_id)

    agents = _agents(tmp_path)
    pipeline = InboundPipeline(
        kernel=_FakeSseKernel(
            events=[
                {"event": "assistant_message", "run_id": "run-1", "content": "done", "origin": "user"},
                {"event": "run_status", "run_id": "run-1", "status": "completed", "origin": "user"},
            ]
        ),
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    pipeline._bg_reply_sender = _sender  # type: ignore[assignment]

    inbound = InboundMessage(
        channel_name="web",
        text="run bg task",
        external_user_id="user-1",
        external_chat_id="chat-bg-f1",
        is_group=False,
    )
    await pipeline.handle_inbound(inbound)
    assert pipeline._bg_subscribers, "subscriber must be created"
    sub = list(pipeline._bg_subscribers.values())[0]
    assert sub._bg_run_output_callback is not None

    # Simulate two BACKGROUND_TASK assistant_message events with the same sequence
    # (replay scenario — gateway restarted and replays from last_sequence=0).
    bg_event = {
        "event": "assistant_message",
        "origin": "background_task",
        "content": "BG result",
        "_id": 42,
        "run_id": "bg-run-1",
    }
    await sub._bg_run_output_callback(bg_event)
    await sub._bg_run_output_callback(bg_event)

    # Both calls produce the same from_session_id (idempotency key is stable).
    assert len(captured) == 2, "callback must fire twice (dedup is IM's job)"
    for fsi in captured:
        assert "|tool_call:" in fsi, (
            f"from_session_id {fsi!r} must contain '|tool_call:' suffix so IM "
            "dedup path (dispatch_request_key) is engaged (bugfix-404 F1)"
        )
    # Both invocations carry identical from_session_id → IM sees same dispatch_request_key.
    assert captured[0] == captured[1], (
        "Replayed event must produce identical from_session_id for IM deduplication"
    )

    await sub.stop()
