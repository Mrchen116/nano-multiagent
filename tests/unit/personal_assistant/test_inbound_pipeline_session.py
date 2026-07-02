"""Inbound pipeline session creation, reuse, binding, and routing tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    build_session_key,
)

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


class _ShadowSync:
    def __init__(self, *, conversation_id: str | None = "shadow-conv-1") -> None:
        self.conversation_id = conversation_id
        self.calls: list[dict[str, object]] = []

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> str | None:
        self.calls.append({"message": message, "agent_id": agent_id})
        return self.conversation_id


def test_inbound_pipeline_runs_four_steps_and_replies_via_origin_channel(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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

    assert result.agent_id == "agent-a"
    assert result.session_key == "web:chat-1:agent-a"
    assert result.kernel_session_id == "sess-1"
    assert result.run_id == "run-1"
    assert result.reply_text == "reply:ping"
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="reply:ping",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        }
    ]
    assert kernel_client.send_calls == [
        {"session_id": "sess-1", "texts": ["ping"], "run_id": "run-1"}
    ]


def test_external_inbound_syncs_user_message_and_seeds_shadow_metadata(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("feishu:agent-a")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    sync = _ShadowSync(conversation_id="shadow-conv-1")
    lifecycle: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        lifecycle.append(
            (
                update.phase,
                update.run_id,
                message.metadata.get("shadow_conversation_id"),
            )
        )

    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        relay_lifecycle_callback=_capture,
        shadow_sync=sync,
    )
    inbound = InboundMessage(
        channel_name="feishu:agent-a",
        text="ping from lark",
        external_user_id="ou_user",
        external_chat_id="oc_feishu_chat",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "oc_feishu_chat",
            "trigger_source": "feishu",
            "sender_display_name": "你",
            "conversation_title": "Agent A · feishu",
        },
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert sync.calls == [{"message": inbound, "agent_id": "agent-a"}]
    assert lifecycle[0] == ("accepted", "run-1", "shadow-conv-1")
    assert channel.sent[0].target_chat_id == "oc_feishu_chat"


def test_external_shadow_sync_failure_does_not_block_or_seed_lazy_direct(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("feishu:agent-a")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    sync = _ShadowSync(conversation_id=None)
    lifecycle: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        lifecycle.append(
            (
                update.phase,
                update.run_id,
                message.metadata.get("shadow_conversation_id"),
            )
        )

    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        relay_lifecycle_callback=_capture,
        shadow_sync=sync,
    )
    inbound = InboundMessage(
        channel_name="feishu:agent-a",
        text="still reply in feishu",
        external_user_id="ou_user",
        external_chat_id="oc_feishu_chat",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "oc_feishu_chat",
            "trigger_source": "feishu",
        },
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert lifecycle[0] == ("accepted", "run-1", None)
    assert channel.sent[0].target_chat_id == "oc_feishu_chat"


def test_inbound_pipeline_passes_local_config_metadata_when_creating_new_kernel_sessions(
    tmp_path: Path,
) -> None:
    """Session metadata uses local agent config for prompt fields; message.metadata
    system_prompt is ignored.  Routing fields (conversation_id, config_profile_version)
    still come from message.metadata."""
    agent_b_dir = tmp_path / "agent-b"
    agent_b_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=tmp_path / "agent-a", title="Agent A"
        ),
        AgentWorkspaceConfig(
            agent_id="agent-b",
            workspace_root=agent_b_dir,
            title="Agent B",
            system_prompt="Local Agent B prompt.",
        ),
    )
    (tmp_path / "agent-a").mkdir(exist_ok=True)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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
        text="ping",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
        agent_id="agent-b",
        metadata={
            "conversation_id": "conv-1",
            "config_profile_version": 2,
            "system_prompt": "Stale relay prompt ignored.",
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agent_b_dir),
            "product_id": "personal_assistant",
            "title": "Agent B",
            "metadata": {
                "agent_id": "agent-b",
                "conversation_id": "conv-1",
                "config_profile_version": 2,
                "system_prompt": "Local Agent B prompt.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        }
    ]


def test_inbound_pipeline_recreates_bound_session_when_workspace_mismatches(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    stale_session_id = "sess-stale"
    kernel_client.seed_session(
        session_id=stale_session_id,
        metadata={"workspace_root": str(agents[1].workspace_root)},
    )
    session_store.bind(
        session_key="web:chat-1:agent-a",
        kernel_session_id=stale_session_id,
        reply_context=None,
    )
    inbound = InboundMessage(
        channel_name="web",
        text="ping",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result.kernel_session_id == "sess-1"
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        }
    ]


def test_inbound_pipeline_emits_running_and_completed_relay_lifecycle_reports_when_message_id_is_present(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    seen: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append((update.phase, update.run_id, message.metadata.get("message_id")))

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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert seen == [
        ("accepted", "run-1", "msg-1"),
        ("running", "run-1", "msg-1"),
        ("completed", "run-1", "msg-1"),
    ]


def test_inbound_pipeline_emits_relay_lifecycle_updates_for_web_relay_messages(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    seen: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append((update.phase, update.run_id, message.metadata.get("message_id")))

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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert seen == [
        ("accepted", "run-1", "msg-1"),
        ("running", "run-1", "msg-1"),
        ("completed", "run-1", "msg-1"),
    ]


def test_inbound_pipeline_emits_real_usage_in_completed_relay_update(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    seen: list[object] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        del message
        if update.phase == "completed":
            seen.append(update.usage)

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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
    )
    kernel_client.run_states["run-1"] = {
        "run_id": "run-1",
        "status": "completed",
        "output_text": "reply:ping",
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert seen == [{"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}]


def test_inbound_pipeline_treats_statusless_run_snapshot_with_output_as_completed(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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
        text="ping",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
    )
    kernel_client.run_states["run-1"] = {"run_id": "run-1", "output_text": "reply:ping"}

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "reply:ping"
    assert channel.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="reply:ping",
            target_chat_id="conv-1",
            thread_id=None,
            metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
        )
    ]


def test_inbound_pipeline_builds_reply_text_from_session_events_when_run_snapshot_has_no_output_text(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    seen: list[tuple[str, str | None, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append(
            (
                update.phase,
                update.run_id,
                message.metadata.get("message_id"),
                update.reply_text,
            )
        )

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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
    )
    kernel_client.session_events["sess-1"] = [
        [
            {"event": "assistant_message", "run_id": "run-old", "content": "ignore me"},
            {"event": "assistant_message", "run_id": "run-1", "content": "Hello"},
        ],
        [
            {"event": "assistant_message", "run_id": "run-1", "content": "Hello world"},
        ],
    ]
    kernel_client.run_states["run-1"] = [
        {"run_id": "run-1", "status": "running"},
        {"run_id": "run-1", "status": "completed", "error": None},
    ]

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "Hello world"
    assert channel.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="Hello world",
            target_chat_id="conv-1",
            thread_id=None,
            metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
        )
    ]
    assert seen == [
        ("accepted", "run-1", "msg-1", None),
        ("running", "run-1", "msg-1", "Hello world"),
        ("completed", "run-1", "msg-1", "Hello world"),
    ]


def test_inbound_pipeline_prefers_completed_run_output_text_over_streamed_text(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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
        text="@agent-a please stay silent if NO_REPLY works.",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={
            "relay_task_id": "relay-1",
            "message_id": "msg-1",
            "mentioned_agent_ids": ["agent-a"],
        },
    )
    kernel_client.session_events["sess-1"] = [
        [
            {
                "id": "evt-1",
                "event": "text_delta",
                "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170"},
            }
        ],
    ]
    kernel_client.run_states["run-1"] = [
        {"run_id": "run-1", "status": "running"},
        {
            "run_id": "run-1",
            "status": "completed",
            "output_text": "NO_REPLY",
            "error": None,
        },
    ]

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
    assert channel.sent == []


def test_inbound_pipeline_prefers_completed_no_reply_token_even_when_streamed_text_arrives_later(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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
        text="@agent-a please stay silent if NO_REPLY works.",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={
            "relay_task_id": "relay-1",
            "message_id": "msg-1",
            "mentioned_agent_ids": ["agent-a"],
        },
    )
    kernel_client.session_events["sess-1"] = [
        [
            {
                "id": "evt-1",
                "event": "text_delta",
                "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170"},
            }
        ],
        [
            {
                "id": "evt-2",
                "event": "text_delta",
                "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170 final"},
            }
        ],
    ]
    kernel_client.run_states["run-1"] = [
        {"run_id": "run-1", "status": "running", "output_text": "NO_REPLY"},
        {
            "run_id": "run-1",
            "status": "completed",
            "output_text": "NO_REPLY",
            "error": None,
        },
    ]

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
    assert channel.sent == []


def _run_group_fanout(
    tmp_path: Path, *, fanout_content: str
) -> tuple[object, _FakeChannel]:
    """Drive a group fan-out turn where a non-target agent (different run_id, non-user
    origin) emits ``fanout_content`` on the streaming other-origin path, while the
    target agent-a returns "reply:demo". Returns (result, channel) so callers assert
    on what was delivered."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
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
        text="@agent-a kick off the markdown demo and @agent-b",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={
            "relay_task_id": "relay-1",
            "message_id": "msg-1",
            "mentioned_agent_ids": ["agent-a"],
        },
    )
    # The fan-out reply rides the other-origin branch of _on_other_event.
    kernel_client.session_events["sess-1"] = [
        [
            {
                "event": "assistant_message",
                "run_id": "run-fanout",
                "origin": "agent",
                "content": fanout_content,
            }
        ],
    ]
    # The target run (agent-a) returns a normal reply.
    kernel_client.run_states["run-1"] = {
        "run_id": "run-1",
        "status": "completed",
        "output_text": "reply:demo",
    }
    result = asyncio.run(pipeline.handle_inbound(inbound))
    return result, channel


def test_group_fanout_other_origin_no_reply_token_is_suppressed(
    tmp_path: Path,
) -> None:
    """bugfix-416 #107: a fan-out (agent-to-agent) assistant_message carrying the
    NO_REPLY sentinel must be suppressed on the streaming other-origin path, exactly
    like the main synchronous reply path. Before the fix only `content.strip()` was
    checked, so the literal `NO_REPLY` leaked into a group bubble."""
    result, channel = _run_group_fanout(tmp_path, fanout_content="NO_REPLY")

    assert result is not None
    # Only the target agent-a reply is delivered; the fan-out NO_REPLY is gone.
    assert [m.text for m in channel.sent] == ["reply:demo"]
    assert "NO_REPLY" not in [m.text for m in channel.sent]


def test_group_fanout_other_origin_non_sentinel_still_delivered(
    tmp_path: Path,
) -> None:
    """bugfix-416 #107 guard: the suppression must not mute genuine fan-out content —
    only the NO_REPLY/HEARTBEAT_OK sentinels are dropped."""
    result, channel = _run_group_fanout(
        tmp_path, fanout_content="Here is the markdown table."
    )

    assert result is not None
    sent = [m.text for m in channel.sent]
    assert "Here is the markdown table." in sent
    assert "reply:demo" in sent


def test_inbound_pipeline_prefers_explicit_agent_then_channel_binding_then_default(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))

    explicit_kernel = _FakeKernel()
    explicit_pipeline = InboundPipeline(
        kernel=explicit_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(
        explicit_pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="explicit",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
                agent_id="agent-b",
            )
        )
    )

    bound_kernel = _FakeKernel()
    bound_pipeline = InboundPipeline(
        kernel=bound_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        channel_bindings={"web:chat-2": "agent-b"},
        default_agent_id="agent-a",
    )
    asyncio.run(
        bound_pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="@agent-b bound",
                external_user_id="user-2",
                external_chat_id="chat-2",
                is_group=True,
                metadata={"mentioned_agent_ids": ["agent-b"], "trigger": "mention"},
            )
        )
    )

    default_kernel = _FakeKernel()
    default_pipeline = InboundPipeline(
        kernel=default_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(
        default_pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="default",
                external_user_id="user-3",
                external_chat_id="chat-3",
                is_group=False,
            )
        )
    )

    assert explicit_kernel.create_session_calls[0]["workspace_root"] == str(
        agents[1].workspace_root
    )
    assert bound_kernel.create_session_calls[0]["workspace_root"] == str(
        agents[1].workspace_root
    )
    assert default_kernel.create_session_calls[0]["workspace_root"] == str(
        agents[0].workspace_root
    )


def test_inbound_pipeline_trusts_group_relay_target_agent_over_mentions(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    result = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent:agent-b please investigate",
                external_user_id="user-1",
                external_chat_id="conv-1",
                is_group=True,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "conv-1",
                    "mentioned_agent_ids": ["agent-b"],
                    "trigger": "mention",
                },
            )
        )
    )

    assert result is None
    assert kernel_client.create_session_calls == []
    assert kernel_client.send_calls == []
    assert channel.sent == []


def test_inbound_pipeline_freezes_group_agent_id_even_without_additional_snapshot_metadata(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    result = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent:agent-b stay quiet",
                external_user_id="user-1",
                external_chat_id="conv-2",
                is_group=True,
                metadata={
                    "conversation_id": "conv-2",
                    "mentioned_agent_ids": ["agent-b"],
                    "trigger": "mention",
                },
            )
        )
    )

    assert result is not None
    assert result.agent_id == "agent-b"
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[1].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent B",
            "metadata": {
                "agent_id": "agent-b",
                "conversation_id": "conv-2",
                "conversation_type": "group",
                "participant_agent_ids": ["agent-b"],
                "external_chat_id": "conv-2",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        }
    ]


def test_inbound_pipeline_reuses_existing_session_binding_per_session_key(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    first = asyncio.run(pipeline.handle_inbound(inbound))
    second = asyncio.run(pipeline.handle_inbound(inbound))

    assert first.kernel_session_id == second.kernel_session_id == "sess-1"
    assert len(kernel_client.create_session_calls) == 1
    assert [call["run_id"] for call in kernel_client.send_calls] == ["run-1", "run-2"]


def test_inbound_pipeline_refreshes_legacy_binding_without_workspace_root(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="pwd一下",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        agent_id="agent-a",
    )
    session_key = build_session_key(inbound, agent_id="agent-a")
    kernel_client.seed_session(
        session_id="sess-legacy", metadata={"agent_id": "agent-a"}
    )
    store.bind(
        session_key=session_key,
        kernel_session_id="sess-legacy",
        reply_context=type(
            "_ReplyContext",
            (),
            {
                "channel_name": "web",
                "target_chat_id": "chat-1",
                "thread_id": None,
                "metadata": {},
            },
        )(),
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.kernel_session_id == "sess-1"
    assert store.get(session_key).kernel_session_id == "sess-1"
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agents[0].workspace_root)
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == ["sess-1"]


def test_register_agent_keeps_existing_direct_sessions_and_uses_new_workspace_for_new_conversations(
    tmp_path: Path,
) -> None:
    agent_a_dir = tmp_path / "agent-a"
    agent_a_dir.mkdir()
    initial_agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=agent_a_dir,
        title="Agent A",
        system_prompt="You are Agent A v1.",
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=(initial_agent,),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )
    old_conversation = InboundMessage(
        channel_name="web",
        text="hello old",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "conversation_id": "chat-1",
            "config_profile_version": 1,
        },
    )

    first = asyncio.run(pipeline.handle_inbound(old_conversation))

    refreshed_workspace = tmp_path / "agent-a-v2"
    refreshed_workspace.mkdir()
    pipeline.register_agent(
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=refreshed_workspace,
            title="Agent A v2",
            system_prompt="You are Agent A v2.",
        )
    )

    second_old = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="hello old again",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "chat-1",
                    "config_profile_version": 2,
                },
            )
        )
    )
    new_conversation = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="hello new",
                external_user_id="user-1",
                external_chat_id="chat-2",
                is_group=False,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "chat-2",
                    "config_profile_version": 2,
                },
            )
        )
    )

    assert first is not None
    assert second_old is not None
    assert new_conversation is not None
    assert first.kernel_session_id == "sess-1"
    assert second_old.kernel_session_id == "sess-2"
    assert new_conversation.kernel_session_id == "sess-3"
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agent_a_dir),
        str(refreshed_workspace),
        str(refreshed_workspace),
    ]
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agent_a_dir),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-1",
                "config_profile_version": 1,
                "system_prompt": "You are Agent A v1.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
        {
            "workspace_root": str(refreshed_workspace),
            "product_id": "personal_assistant",
            "title": "Agent A v2",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-1",
                "config_profile_version": 2,
                "system_prompt": "You are Agent A v2.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
        {
            "workspace_root": str(refreshed_workspace),
            "product_id": "personal_assistant",
            "title": "Agent A v2",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-2",
                "config_profile_version": 2,
                "system_prompt": "You are Agent A v2.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
    ]
    # Outbound metadata passes through message.metadata verbatim (routing fields only).
    assert channel.sent[1].metadata == {
        "conversation_id": "chat-1",
        "config_profile_version": 2,
    }
    assert channel.sent[2].metadata == {
        "conversation_id": "chat-2",
        "config_profile_version": 2,
    }
