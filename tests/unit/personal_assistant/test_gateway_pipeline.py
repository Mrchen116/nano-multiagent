"""Gateway channel system and inbound pipeline tests for milestone M100."""

from __future__ import annotations

import asyncio
from pathlib import Path


from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore, build_session_key


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started_with = None
        self.stopped = 0
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):
        self.started_with = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        self.stopped += 1


class _FakeKernelClient:
    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, list[dict[str, str]] | dict[str, str]] = {}
        self.session_events: dict[str, list[list[dict[str, object]]]] = {}
        self._session_metadata_by_id: dict[str, dict[str, object]] = {}
        self._session_index = 0
        self._run_index = 0
        self._get_run_calls: dict[str, int] = {}
        self._stream_calls: dict[str, int] = {}

    def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ):
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title, "metadata": metadata}
        )
        self._session_metadata_by_id[session_id] = {**dict(metadata or {}), "workspace_root": workspace_root}
        self.session_events.setdefault(session_id, [])
        return {"session_id": session_id}

    def get_session(self, *, session_id: str):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {"session_id": session_id, "status": "active", "created_at": "now", "metadata": dict(metadata)}

    def seed_session(self, *, session_id: str, metadata: dict[str, object] | None = None) -> None:
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        self.run_states.setdefault(run_id, {"run_id": run_id, "status": "completed", "output_text": f"reply:{text}"})
        self.session_events.setdefault(session_id, [])
        return {"run_id": run_id}

    def stream_session_events(self, *, session_id: str, max_events: int = 20, timeout_seconds: float = 0.25):
        del max_events
        del timeout_seconds
        batches = self.session_events.get(session_id, [])
        index = self._stream_calls.get(session_id, 0)
        self._stream_calls[session_id] = index + 1
        if index >= len(batches):
            return []
        return batches[index]

    def get_run(self, *, run_id: str):
        payload = self.run_states[run_id]
        if isinstance(payload, list):
            index = self._get_run_calls.get(run_id, 0)
            self._get_run_calls[run_id] = index + 1
            if index >= len(payload):
                return payload[-1]
            return payload[index]
        return payload


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    agent_a.mkdir()
    agent_b.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agent_a, title="Agent A"),
        AgentWorkspaceConfig(agent_id="agent-b", workspace_root=agent_b, title="Agent B"),
    )


def test_channel_registry_and_bootstrap_manage_adapter_lifecycle() -> None:
    channel_a = _FakeChannel("web")
    channel_b = _FakeChannel("qq")
    registry = ChannelRegistry((channel_a, channel_b))
    seen: list[InboundMessage] = []

    started = start_channels(registry, seen.append)
    stopped = stop_channels(registry)

    assert started == ("web", "qq")
    assert channel_a.started_with is not None
    assert channel_b.started_with is not None
    assert stopped == ("qq", "web")
    assert channel_a.stopped == 1
    assert channel_b.stopped == 1


def test_build_session_key_uses_chat_id_for_groups_and_direct_messages() -> None:
    group_message = InboundMessage(
        channel_name="web",
        text="hello group",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=True,
    )
    direct_message = InboundMessage(
        channel_name="web",
        text="hello dm",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    assert build_session_key(group_message, agent_id="agent-a") == "web:chat-1:agent-a"
    assert build_session_key(direct_message, agent_id="agent-a") == "web:chat-1:agent-a"


def test_inbound_pipeline_runs_four_steps_and_replies_via_origin_channel(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
            "metadata": None,
        }
    ]
    assert kernel_client.send_calls == [{"session_id": "sess-1", "text": "ping", "run_id": "run-1"}]


def test_inbound_pipeline_passes_frozen_prompt_metadata_when_creating_new_kernel_sessions(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
            "system_prompt": "You are Agent B v2.",
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[1].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent B",
            "metadata": {
                "agent_id": "agent-b",
                "conversation_id": "conv-1",
                "config_profile_version": 2,
                "system_prompt": "You are Agent B v2.",
            },
        }
    ]


def test_inbound_pipeline_emits_running_and_completed_relay_lifecycle_reports_when_message_id_is_present(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    seen: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append((update.phase, update.run_id, message.metadata.get("message_id")))

    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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


def test_inbound_pipeline_emits_relay_lifecycle_updates_for_web_relay_messages(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    seen: list[tuple[str, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append((update.phase, update.run_id, message.metadata.get("message_id")))

    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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


def test_inbound_pipeline_emits_real_usage_in_completed_relay_update(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    seen: list[object] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        del message
        if update.phase == "completed":
            seen.append(update.usage)

    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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



def test_inbound_pipeline_treats_statusless_run_snapshot_with_output_as_completed(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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



def test_inbound_pipeline_builds_reply_text_from_session_events_when_run_snapshot_has_no_output_text(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    seen: list[tuple[str, str | None, str | None, str | None]] = []

    async def _capture(message: InboundMessage, update) -> None:  # noqa: ANN001
        seen.append((update.phase, update.run_id, message.metadata.get("message_id"), update.reply_text))

    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
            {"id": "evt-old", "event": "text_delta", "data": {"run_id": "run-old", "delta": "ignore me"}},
            {"id": "evt-1", "event": "text_delta", "data": {"run_id": "run-1", "delta": "Hello"}},
        ],
        [
            {"id": "evt-1", "event": "text_delta", "data": {"run_id": "run-1", "delta": "Hello"}},
            {"id": "evt-2", "event": "text_delta", "data": {"run_id": "run-1", "delta": " world"}},
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


def test_inbound_pipeline_prefers_completed_run_output_text_over_streamed_text(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1", "mentioned_agent_ids": ["agent-a"]},
    )
    kernel_client.session_events["sess-1"] = [
        [{"id": "evt-1", "event": "text_delta", "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170"}}],
    ]
    kernel_client.run_states["run-1"] = [
        {"run_id": "run-1", "status": "running"},
        {"run_id": "run-1", "status": "completed", "output_text": "NO_REPLY", "error": None},
    ]

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
    assert channel.sent == []


def test_inbound_pipeline_prefers_completed_no_reply_token_even_when_streamed_text_arrives_later(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
        metadata={"relay_task_id": "relay-1", "message_id": "msg-1", "mentioned_agent_ids": ["agent-a"]},
    )
    kernel_client.session_events["sess-1"] = [
        [{"id": "evt-1", "event": "text_delta", "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170"}}],
        [{"id": "evt-2", "event": "text_delta", "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170 final"}}],
    ]
    kernel_client.run_states["run-1"] = [
        {"run_id": "run-1", "status": "running", "output_text": "NO_REPLY"},
        {"run_id": "run-1", "status": "completed", "output_text": "NO_REPLY", "error": None},
    ]

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
    assert channel.sent == []


def test_inbound_pipeline_prefers_explicit_agent_then_channel_binding_then_default(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))

    explicit_kernel = _FakeKernelClient()
    explicit_pipeline = InboundPipeline(
        kernel_client=explicit_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(explicit_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="explicit",
            external_user_id="user-1",
            external_chat_id="chat-1",
            is_group=False,
            agent_id="agent-b",
        )
    ))

    bound_kernel = _FakeKernelClient()
    bound_pipeline = InboundPipeline(
        kernel_client=bound_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        channel_bindings={"web:chat-2": "agent-b"},
        default_agent_id="agent-a",
    )
    asyncio.run(bound_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="@agent-b bound",
            external_user_id="user-2",
            external_chat_id="chat-2",
            is_group=True,
            metadata={"mentioned_agent_ids": ["agent-b"], "trigger": "mention"},
        )
    ))

    default_kernel = _FakeKernelClient()
    default_pipeline = InboundPipeline(
        kernel_client=default_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(default_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="default",
            external_user_id="user-3",
            external_chat_id="chat-3",
            is_group=False,
        )
    ))

    assert explicit_kernel.create_session_calls[0]["workspace_root"] == str(agents[1].workspace_root)
    assert bound_kernel.create_session_calls[0]["workspace_root"] == str(agents[1].workspace_root)
    assert default_kernel.create_session_calls[0]["workspace_root"] == str(agents[0].workspace_root)


def test_inbound_pipeline_prefers_group_mentions_over_drifted_explicit_agent_ids(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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

    assert result.agent_id == "agent-b"
    assert result.session_key == "web_relay:conv-1:agent-b"
    assert kernel_client.create_session_calls[0]["workspace_root"] == str(agents[1].workspace_root)
    assert kernel_client.create_session_calls[0]["metadata"] == {
        "agent_id": "agent-b",
        "conversation_id": "conv-1",
    }
    assert kernel_client.send_calls == [{"session_id": "sess-1", "text": "@agent:agent-b please investigate", "run_id": "run-1"}]


def test_inbound_pipeline_freezes_group_agent_id_even_without_additional_snapshot_metadata(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
            },
        }
    ]


def test_inbound_pipeline_reuses_existing_session_binding_per_session_key(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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



def test_inbound_pipeline_refreshes_legacy_binding_without_workspace_root(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
    kernel_client.seed_session(session_id="sess-legacy", metadata={"agent_id": "agent-a"})
    store.bind(
        session_key=session_key,
        kernel_session_id="sess-legacy",
        reply_context=type(
            "_ReplyContext",
            (),
            {"channel_name": "web", "target_chat_id": "chat-1", "thread_id": None, "metadata": {}},
        )(),
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.kernel_session_id == "sess-1"
    assert store.get(session_key).kernel_session_id == "sess-1"
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [str(agents[0].workspace_root)]
    assert [call["session_id"] for call in kernel_client.send_calls] == ["sess-1"]


def test_register_agent_keeps_existing_direct_sessions_and_uses_new_workspace_for_new_conversations(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=(agents[0],),
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
            "system_prompt": "You are Agent A v1.",
        },
    )

    first = asyncio.run(pipeline.handle_inbound(old_conversation))

    refreshed_workspace = tmp_path / "agent-a-v2"
    refreshed_workspace.mkdir()
    pipeline.register_agent(
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=refreshed_workspace, title="Agent A v2")
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
                    "system_prompt": "You are Agent A v2.",
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
                    "system_prompt": "You are Agent A v2.",
                },
            )
        )
    )

    assert first is not None
    assert second_old is not None
    assert new_conversation is not None
    assert first.kernel_session_id == "sess-1"
    assert second_old.kernel_session_id == "sess-1"
    assert new_conversation.kernel_session_id == "sess-2"
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agents[0].workspace_root),
        str(refreshed_workspace),
    ]
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-1",
                "config_profile_version": 1,
                "system_prompt": "You are Agent A v1.",
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
            },
        },
    ]
    assert channel.sent[1].metadata == {
        "conversation_id": "chat-1",
        "config_profile_version": 2,
        "system_prompt": "You are Agent A v2.",
    }
    assert channel.sent[2].metadata == {
        "conversation_id": "chat-2",
        "config_profile_version": 2,
        "system_prompt": "You are Agent A v2.",
    }


def test_drop_agent_sessions_forces_group_mentions_to_create_a_fresh_kernel_session(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=(agents[0],),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )

    first = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent-a first pass",
                external_user_id="user-1",
                external_chat_id="conv-group-1",
                is_group=True,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "conv-group-1",
                    "mentioned_agent_ids": ["agent-a"],
                    "trigger": "mention",
                    "config_profile_version": 1,
                    "system_prompt": "Reply with ALPHA_ACK_M170.",
                },
            )
        )
    )

    pipeline.register_agent(
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agents[0].workspace_root, title="Agent A")
    )
    pipeline.drop_agent_sessions("agent-a")

    second = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent-a second pass",
                external_user_id="user-1",
                external_chat_id="conv-group-1",
                is_group=True,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "conv-group-1",
                    "mentioned_agent_ids": ["agent-a"],
                    "trigger": "mention",
                    "config_profile_version": 2,
                    "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
                },
            )
        )
    )

    assert first is not None
    assert second is not None
    assert first.kernel_session_id == "sess-1"
    assert second.kernel_session_id == "sess-2"
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "conv-group-1",
                "config_profile_version": 1,
                "system_prompt": "Reply with ALPHA_ACK_M170.",
            },
        },
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "conv-group-1",
                "config_profile_version": 2,
                "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
            },
        },
    ]


def test_session_run_queue_serializes_same_session_and_allows_cross_session_parallelism() -> None:
    queue = SessionRunQueue()
    events: list[str] = []
    same_session_active = 0
    same_session_peak = 0
    cross_session_active = 0
    cross_session_peak = 0
    gate = asyncio.Event()
    second_started = asyncio.Event()

    async def same_session_job(name: str) -> str:
        nonlocal same_session_active, same_session_peak
        same_session_active += 1
        same_session_peak = max(same_session_peak, same_session_active)
        events.append(f"start:{name}")
        if name == "one":
            await gate.wait()
        else:
            second_started.set()
        await asyncio.sleep(0)
        events.append(f"end:{name}")
        same_session_active -= 1
        return name

    async def exercise_queue() -> tuple[list[str], int, int, list[str]]:
        first_task = asyncio.create_task(queue.submit("sess-a", lambda: same_session_job("one")))
        await asyncio.sleep(0)
        second_task = asyncio.create_task(queue.submit("sess-a", lambda: same_session_job("two")))
        await asyncio.sleep(0.01)
        assert not second_started.is_set()
        gate.set()
        first_result = await first_task
        second_result = await second_task

        async def cross_session_job(name: str) -> str:
            nonlocal cross_session_active, cross_session_peak
            cross_session_active += 1
            cross_session_peak = max(cross_session_peak, cross_session_active)
            await asyncio.sleep(0.02)
            cross_session_active -= 1
            return name

        parallel_results = await asyncio.gather(
            queue.submit("sess-b", lambda: cross_session_job("b")),
            queue.submit("sess-c", lambda: cross_session_job("c")),
        )
        return events, same_session_peak, cross_session_peak, [first_result, second_result, *parallel_results]

    recorded_events, same_peak, cross_peak, results = asyncio.run(exercise_queue())

    assert same_peak == 1
    assert recorded_events == ["start:one", "end:one", "start:two", "end:two"]
    assert results == ["one", "two", "b", "c"]
    assert cross_peak >= 2
