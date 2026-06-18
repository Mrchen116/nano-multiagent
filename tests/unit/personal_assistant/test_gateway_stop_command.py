"""Gateway /stop command tests for feat-332."""

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
from personal_assistant.gateway.session_keys import SessionBindingStore
from ._pipeline_helpers import _FakeKernel


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


def test_stop_ack_delivered_via_bg_reply_sender_when_wired(tmp_path: Path) -> None:
    """bugfix-417-fix2 (#114, Issue 2): when the live delivery sender is wired, the
    /stop ack must go through _bg_reply_sender (the real send_agent_message WS path),
    NOT the no-op outbound_router.send_text — otherwise the friendly message never
    reaches IM (journey 13)."""
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

    delivered: list[tuple[str, str]] = []

    async def _fake_bg_sender(text, reply_context, from_session_id):
        delivered.append((text, from_session_id))

    pipeline._bg_reply_sender = _fake_bg_sender

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
    assert delivered[0][1].startswith("agent-a|tool_call:") and delivered[0][1].endswith(":stop-noop")
    assert channel.sent == [], "must NOT use the no-op send_text when sender is wired"


def test_stop_command_interrupts_active_run_and_appends_message(tmp_path: Path) -> None:
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
    # Seed an existing session binding so /stop can resolve the kernel session.
    session_key = "web:chat-1:agent-a"
    kernel_client.seed_session = lambda session_id, metadata=None: None
    kernel_client._session_metadata_by_id["sess-1"] = {
        "workspace_root": str(agents[0].workspace_root)
    }

    # Simulate an active run by injecting it directly.
    pipeline._active_runs[session_key] = "run-active"

    inbound = InboundMessage(
        channel_name="web",
        text="/stop",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "已停止当前操作。"
    assert result.run_id == "run-active"
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="已停止当前操作。",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
    assert len(kernel_client.interrupt_calls) == 1
    assert kernel_client.interrupt_calls[0]["session_id"] == "sess-1"
    # M3: /stop logs via kernel.submit (in send_calls) instead of append_message.
    stop_submits = [
        c
        for c in kernel_client.send_calls
        if any("stop" in t.lower() or "终止" in t for t in c.get("texts", []))
    ]
    assert len(stop_submits) == 1
    assert stop_submits[0]["session_id"] == "sess-1"
    assert "用户发送了 /stop 命令，要求终止当前操作。" in stop_submits[0]["texts"]


def test_stop_command_in_group_chat_with_mention_is_recognized(tmp_path: Path) -> None:
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
    session_key = "web_relay:grp-1:agent-a"
    kernel_client._session_metadata_by_id["sess-1"] = {
        "workspace_root": str(agents[0].workspace_root)
    }
    pipeline._active_runs[session_key] = "run-active"

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
    assert result.reply_text == "已停止当前操作。"
    assert len(kernel_client.interrupt_calls) == 1


def test_stop_command_with_agent_after_slash_is_recognized(tmp_path: Path) -> None:
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
    session_key = "web_relay:grp-1:agent-a"
    kernel_client._session_metadata_by_id["sess-1"] = {
        "workspace_root": str(agents[0].workspace_root)
    }
    pipeline._active_runs[session_key] = "run-active"

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
    assert result.reply_text == "已停止当前操作。"
    assert len(kernel_client.interrupt_calls) == 1


def test_stop_command_does_not_enter_group_context_buffer(tmp_path: Path) -> None:
    from personal_assistant.gateway.group_context_store import GroupContextStore

    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    group_store = GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3")
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        group_context_store=group_store,
    )
    session_key = "web_relay:grp-1:agent-a"
    kernel_client._session_metadata_by_id["sess-1"] = {
        "workspace_root": str(agents[0].workspace_root)
    }
    pipeline._active_runs[session_key] = "run-active"

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
    buf_key = pipeline._group_buf_key_for_agent(inbound, "agent-a")
    assert group_store.drain(buf_key) == []


def test_active_run_tracking_registers_and_unregisters(tmp_path: Path) -> None:
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

    assert result is not None
    session_key = "web:chat-1:agent-a"
    # After the run completes, active run tracking should be cleared.
    assert session_key not in pipeline._active_runs
