"""Gateway /stop command tests for feat-332."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import build_group_context_key
from tests.helpers.inbound_pipeline import build_inbound_pipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from ._pipeline_helpers import _FakeKernel
from ._session_run_coordinator_helpers import ControlledKernel


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
        self.send_calls: list[dict[str, object]] = []
        self.interrupt_calls: list[dict[str, str]] = []
        self.append_calls: list[dict[str, object]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self._session_metadata_by_id: dict[str, dict[str, object]] = {}
        self._session_index = 0
        self._run_index = 0

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
            {
                "workspace_root": workspace_root,
                "product_id": product_id,
                "title": title,
                "metadata": metadata,
            }
        )
        self._session_metadata_by_id[session_id] = {
            **dict(metadata or {}),
            "workspace_root": workspace_root,
        }
        return {"session_id": session_id}

    def get_session(self, *, session_id: str, **_kwargs):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": "now",
            "metadata": dict(metadata),
        }

    def submit_message(
        self, *, session_id: str, texts: list[str], image_urls=None, **_kwargs
    ):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        text = texts[-1] if texts else ""
        call: dict = {"session_id": session_id, "texts": texts, "run_id": run_id}
        if image_urls is not None:
            call["image_urls"] = image_urls
        self.send_calls.append(call)
        self.run_states.setdefault(
            run_id,
            {"run_id": run_id, "status": "completed", "output_text": f"reply:{text}"},
        )
        return {
            "run_id": run_id,
            "anchor_sequence": 1,
            "injected": False,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id, last_event_id=None, workspace_root=None, **_kwargs
    ):
        run_id = self.send_calls[-1]["run_id"] if self.send_calls else "run-1"
        text = self.run_states.get(run_id, {}).get("output_text", "")
        yield {"event": "assistant_message", "run_id": run_id, "content": text}
        yield {
            "event": "run_status",
            "run_id": run_id,
            "status": "completed",
            "output_text": text,
        }

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]

    def interrupt_session(self, *, session_id: str, **_kwargs):
        self.interrupt_calls.append({"session_id": session_id})
        return {"session_id": session_id, "interrupted": True, "run_id": "run-active"}

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        turn_id: str | None = None,
        parts: list[dict[str, object]] | None = None,
        metadata: dict[str, object] | None = None,
        idempotency_key: str | None = None,
        **_kwargs,
    ):
        self.append_calls.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "message_id": message_id,
                "turn_id": turn_id,
                "parts": parts,
                "metadata": metadata,
                "idempotency_key": idempotency_key,
            }
        )
        return {
            "session_id": session_id,
            "entry_id": "entry-1",
            "kind": "turn_appended",
            "created_at": "now",
            "turn_id": "",
            "role": role,
            "content": content,
        }


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    agent_a.mkdir()
    agent_b.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=agent_a, title="Agent A"
        ),
        AgentWorkspaceConfig(
            agent_id="agent-b", workspace_root=agent_b, title="Agent B"
        ),
    )


def test_stop_command_with_no_active_run_returns_friendly_message(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="/stop",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "当前没有正在执行的操作。"
    assert result.run_id == ""
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="当前没有正在执行的操作。",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
    assert kernel_client.interrupt_calls == []
    # M3: no message submitted when there is no active run to stop
    stop_text_calls = [
        c
        for c in kernel_client.send_calls
        if any("stop" in t.lower() for t in c.get("texts", []))
    ]
    assert stop_text_calls == []


def test_new_command_replaces_the_current_binding_without_erasing_the_chat(
    tmp_path: Path,
) -> None:
    """`/new` keeps the channel target but gives the next turn a new session."""

    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    first = InboundMessage(
        channel_name="web",
        text="continue the old task",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    assert asyncio.run(pipeline.handle_inbound(first)) is not None

    result = asyncio.run(pipeline.handle_inbound(replace(first, text="/new")))

    assert result is not None
    assert result.reply_text == "已开始新会话。"
    assert result.kernel_session_id == "sess-2"
    assert [call["session_id"] for call in kernel.send_calls] == ["sess-1"]
    assert [call["workspace_root"] for call in kernel.create_session_calls] == [
        str(agents[0].workspace_root),
        str(agents[0].workspace_root),
    ]
    assert channel.sent[-1].text == "已开始新会话。"


def test_new_requires_an_explicit_group_target_but_stop_remains_the_exception(
    tmp_path: Path,
) -> None:
    agents = _mention_agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    bare = InboundMessage(
        channel_name="web_relay",
        text="/new",
        external_user_id="user-1",
        external_chat_id="group-1",
        is_group=True,
    )
    mentioned = replace(
        bare,
        text="@agent-a /new",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    assert asyncio.run(pipeline.handle_inbound(bare)) is None
    result = asyncio.run(pipeline.handle_inbound(mentioned))

    assert result is not None
    assert result.reply_text == "已开始新会话。"
    assert len(kernel.create_session_calls) == 1


def test_implicit_external_shadow_target_cannot_authorize_group_controls(
    tmp_path: Path,
) -> None:
    """Synthetic shadow routing must not impersonate a user @ mention for `/new`."""

    agents = _mention_agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    synthetic = InboundMessage(
        channel_name="web_relay",
        text="/compact",
        external_user_id="user-1",
        external_chat_id="group-1",
        is_group=True,
        agent_id="agent-a",
        metadata={
            "mentioned_agent_ids": ["agent-a"],
            "implicit_external_agent_target": True,
        },
    )

    assert asyncio.run(pipeline.handle_inbound(synthetic)) is None
    assert kernel.create_session_calls == []
    assert kernel.compact_calls == []


def test_new_replay_with_a_stable_ingress_id_does_not_create_another_session(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="/new",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={"relay_task_id": "relay-new-1"},
    )

    first = asyncio.run(pipeline.handle_inbound(inbound))
    second = asyncio.run(pipeline.handle_inbound(inbound))

    assert first is not None and second is not None
    assert first.kernel_session_id == second.kernel_session_id == "sess-1"
    assert len(kernel.create_session_calls) == 1


def test_new_ack_uses_an_im_dispatch_identity_that_the_web_relay_accepts(
    tmp_path: Path,
) -> None:
    """A `/new` reply is visible in Web IM instead of being rejected as malformed."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, _reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline = build_inbound_pipeline(
        kernel=_FakeKernel(),
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        bg_reply_sender=_fake_bg_sender,
    )
    result = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="/new",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
                metadata={"relay_task_id": "relay-new-1"},
            )
        )
    )

    assert result is not None
    assert delivered == [
        (
            "已开始新会话。",
            "agent-a|tool_call:control:new-ack:relay:relay-new-1",
        )
    ]


def test_compact_with_focus_uses_the_current_binding_without_creating_a_turn(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    first = InboundMessage(
        channel_name="web",
        text="work before a transition",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    assert asyncio.run(pipeline.handle_inbound(first)) is not None

    result = asyncio.run(
        pipeline.handle_inbound(
            replace(
                first,
                text="/compact 保留认证方案与未完成项",
                metadata={"relay_task_id": "relay-compact-1"},
            )
        )
    )
    replay = asyncio.run(
        pipeline.handle_inbound(
            replace(
                first,
                text="/compact 保留认证方案与未完成项",
                metadata={"relay_task_id": "relay-compact-1"},
            )
        )
    )

    assert result is not None and replay is not None
    assert result.reply_text == "已按关注点压缩当前会话。"
    assert replay.reply_text == result.reply_text
    assert kernel.compact_calls == [
        {
            "session_id": "sess-1",
            "workspace_root": str(agents[0].workspace_root),
            "focus": "保留认证方案与未完成项",
            "idempotency_key": "relay:relay-compact-1",
        }
    ]
    assert [call["session_id"] for call in kernel.send_calls] == ["sess-1"]


def test_compact_without_a_current_binding_does_not_create_an_empty_session(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    result = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="/compact",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
            )
        )
    )

    assert result is not None
    assert result.reply_text == "当前历史不足，无需压缩。"
    assert kernel.create_session_calls == []
    assert kernel.compact_calls == []


def test_stop_ack_delivered_via_bg_reply_sender_when_wired(tmp_path: Path) -> None:
    """bugfix-417-fix2 (#114, Issue 2): when the live delivery sender is wired, the
    /stop ack must go through _bg_reply_sender (the real send_agent_message WS path),
    NOT the no-op outbound_router.send_text — otherwise the friendly message never
    reaches IM (journey 13)."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        bg_reply_sender=_fake_bg_sender,
    )

    inbound = InboundMessage(
        channel_name="web",
        text="/stop",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "当前没有正在执行的操作。"
    # Delivered through the live sender, not the no-op router.
    assert len(delivered) == 1
    assert delivered[0][0] == "当前没有正在执行的操作。"
    assert delivered[0][1].startswith("agent-a|tool_call:") and delivered[0][
        1
    ].endswith(":stop-noop")
    assert channel.sent == [], "must NOT use the no-op send_text when sender is wired"


def test_repeated_feishu_stop_noop_uses_per_message_im_dedupe_key(
    tmp_path: Path,
) -> None:
    """Each real Feishu /stop message needs its own IM shadow acknowledgement.

    The IM side deduplicates agent messages by ``from_session_id``.  If every
    no-op /stop in the same kernel session uses the same key, only the first
    acknowledgement is visible in the shadow conversation while Feishu still
    gets each reply.
    """
    agents = _agents(tmp_path)
    channel = _FakeChannel("feishu:agent-a")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        bg_reply_sender=_fake_bg_sender,
    )

    for message_id in ("om_stop_1", "om_stop_2"):
        inbound = InboundMessage(
            channel_name="feishu:agent-a",
            text="/stop",
            external_user_id="ou-user",
            external_chat_id="feishu:app:dm:ou-user",
            is_group=False,
            agent_id="agent-a",
            metadata={
                "external_source": "feishu",
                "external_chat_id": "feishu:app:dm:ou-user",
                "trigger_source": "feishu",
                "shadow_conversation_id": "conv-shadow",
                "feishu_message_id": message_id,
            },
        )
        result = asyncio.run(pipeline.handle_inbound(inbound))
        assert result is not None
        assert result.reply_text == "当前没有正在执行的操作。"

    assert [text for text, _ in delivered] == [
        "当前没有正在执行的操作。",
        "当前没有正在执行的操作。",
    ]
    assert delivered[0][1] != delivered[1][1]
    assert delivered[0][1].endswith(":stop-noop:om_stop_1")
    assert delivered[1][1].endswith(":stop-noop:om_stop_2")


@pytest.mark.asyncio
async def test_stop_command_interrupts_active_run_and_appends_message(
    tmp_path: Path,
) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = ControlledKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    running = asyncio.create_task(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="work",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
            )
        )
    )
    await kernel.wait_stream("run-1")
    stopped = await pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="/stop",
            external_user_id="user-1",
            external_chat_id="chat-1",
            is_group=False,
        )
    )
    kernel.finish("run-1", status="cancelled", text="")
    completed = await running

    assert stopped is not None
    assert stopped.reply_text == "已停止当前操作。"
    assert stopped.run_id == "run-1"
    assert completed is not None
    assert completed.outbound is None
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="已停止当前操作。",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
    assert kernel.interrupt_calls == ["sess-1"]
    assert kernel.append_calls == [
        {
            "session_id": "sess-1",
            "role": "user",
            "content": "[Request interrupted by user for tool use]",
        }
    ]


def test_stop_command_in_group_chat_with_mention_is_recognized(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="@agent-a /stop",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    result = asyncio.run(pipeline.handle_inbound(inbound))
    assert result is not None
    assert result.run_id == ""
    assert kernel.create_session_calls == []


def test_stop_command_with_structured_feishu_display_mention_is_recognized(
    tmp_path: Path,
) -> None:
    """Feishu display mention may be @nano, not @{agent_id}; metadata owns targeting."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("feishu:agent-a")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="feishu:agent-a",
        text="@nano /stop",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        metadata={
            "mentioned_agent_ids": ["agent-a"],
            "feishu_mentions": [
                {"open_id": "ou_bot", "name": "nano", "key": "@_user_1"}
            ],
        },
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.run_id == ""
    assert kernel_client.create_session_calls == []


def test_stop_command_with_agent_after_slash_is_recognized(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="/stop @agent-a",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.run_id == ""
    assert kernel_client.create_session_calls == []


def test_stop_command_does_not_enter_group_context_buffer(tmp_path: Path) -> None:
    from personal_assistant.gateway.group_context_store import GroupContextStore

    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    group_store = GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3")
    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        group_context_store=group_store,
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="@agent-a /stop",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    buf_key = build_group_context_key(inbound, "agent-a")
    assert group_store.drain(buf_key) == []


# ---------------------------------------------------------------------------
# feat-430: 群聊裸 /stop（无 @）不受 MENTION 投递策略限制；对未运行 agent 无副作用。
# ---------------------------------------------------------------------------


def _mention_agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_a.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=agent_a,
            title="Agent A",
            group_reply_policy="MENTION",
        ),
    )


def _two_mention_agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    out = []
    for name in ("agent-a", "agent-b"):
        d = tmp_path / name
        d.mkdir()
        out.append(
            AgentWorkspaceConfig(
                agent_id=name,
                workspace_root=d,
                title=name,
                group_reply_policy="MENTION",
            )
        )
    return tuple(out)


@pytest.mark.asyncio
async def test_bare_stop_in_group_multi_agent_stops_only_running_no_noise(
    tmp_path: Path,
) -> None:
    """群聊裸 /stop 广播到每个成员（各自 relay）：只有正在运行的 agent 被停止，
    未运行的 agent 既不被 interrupt 也不发 no-op ack（spec 幂等/无副作用）。"""
    agents = _two_mention_agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = ControlledKernel()
    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        bg_reply_sender=_fake_bg_sender,
    )
    running = asyncio.create_task(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent-a work",
                external_user_id="user-1",
                external_chat_id="grp-1",
                is_group=True,
                agent_id="agent-a",
                metadata={"mentioned_agent_ids": ["agent-a"]},
            )
        )
    )
    await kernel.wait_stream("run-1")

    # The group /stop is relayed to each member agent separately (IM fan-out).
    for agent_id in ("agent-a", "agent-b"):
        msg = InboundMessage(
            channel_name="web_relay",
            text="/stop",
            external_user_id="user-1",
            external_chat_id="grp-1",
            is_group=True,
            agent_id=agent_id,
            metadata={"mentioned_agent_ids": []},
        )
        await pipeline.handle_inbound(msg)
    kernel.finish("run-1", status="cancelled", text="")
    await running

    # Exactly one interrupt — the running agent-a.
    assert kernel.interrupt_calls == ["sess-1"]
    # Only the running agent's "已停止当前操作。" ack; no no-op noise from idle agent-b.
    assert delivered == [t for t in delivered if t[0] == "已停止当前操作。"]
    assert [t[0] for t in delivered] == ["已停止当前操作。"]
    assert all("当前没有正在执行" not in t[0] for t in delivered)
    assert channel.sent == []
    # fix-r2 (code-review P1.5): the idle member (agent-b) must NOT get a kernel session.
    assert kernel.create_calls == [str(agents[0].workspace_root)]


def test_bare_stop_in_group_no_active_run_has_no_side_effect(tmp_path: Path) -> None:
    """裸 /stop 对未运行的群成员 agent 幂等：不发 no-op ack、不被缓存为群上下文。"""
    from personal_assistant.gateway.group_context_store import GroupContextStore

    agents = _mention_agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel_client = _FakeKernel()
    group_store = GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3")
    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        group_context_store=group_store,
        bg_reply_sender=_fake_bg_sender,
    )
    # No active run for this agent.

    inbound = InboundMessage(
        channel_name="web_relay",
        text="/stop",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        metadata={"mentioned_agent_ids": []},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert kernel_client.interrupt_calls == []
    # No friendly no-op ack bubble for a non-running group agent (无副作用).
    assert delivered == []
    assert channel.sent == []
    # fix-r2 (code-review P1.5): idle group member must NOT allocate a kernel session.
    assert kernel_client.create_session_calls == []
    # /stop is a control command — it must not be buffered as group context.
    buf_key = build_group_context_key(inbound, "agent-a")
    assert group_store.drain(buf_key) == []
