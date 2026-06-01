"""Inbound pipeline SSE path tests (feat-338 cutover) and map_kernel_event mapping."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel, _FakeSseKernel, _agents


def test_inbound_pipeline_uses_sse_path_when_submit_and_stream_available(tmp_path: Path) -> None:
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


def test_inbound_pipeline_sse_path_extracts_reply_from_assistant_message(tmp_path: Path) -> None:
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
            {"event": "run_status", "run_id": "run-1", "status": "failed", "error": "boom"},
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


def test_inbound_pipeline_sse_path_routes_non_user_origin_events(tmp_path: Path) -> None:
    """Events with origin != user and mismatched run_id are routed outbound.

    This verifies the session_key serial queue handles background-wake / cron
    events while the user run is in progress.
    """
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-other", "content": "background", "origin": "background_task"},
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


def test_inbound_pipeline_sse_path_relay_lifecycle_emits_completed_with_usage(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeSseKernel(
        events=[
            {"event": "assistant_message", "run_id": "run-1", "content": "ok"},
            {"event": "run_status", "run_id": "run-1", "status": "completed", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
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
    assert seen[-1].usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}


def test_map_kernel_event_to_run_activity() -> None:
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "run_status", "status": "running"}) == "agent.run.started"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "run_status", "status": "completed"}) == "agent.run.completed"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "run_status", "status": "failed"}) == "agent.run.failed"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "run_status", "status": "cancelled"}) == "agent.run.failed"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "assistant_message"}) == "agent.text.message"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "tool_start"}) == "agent.tool.started"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "tool_end"}) == "agent.tool.completed"
    assert InboundPipeline._map_kernel_event_to_run_activity({"event": "turn_end"}) is None
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
            stream_calls.append({"session_id": session_id, "after_sequence": after_sequence})
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
