"""M103 gateway-side mention gating and local-autonomy coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):  # noqa: ANN001
        self.on_inbound = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        return None


class _FakeKernelClient:
    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, str | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self.default_output_text = "reply:{text}"
        self._session_index = 0
        self._run_index = 0

    def create_session(self, *, workspace_root: str, product_id: str, title: str | None = None):
        self._session_index += 1
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title}
        )
        return {"session_id": f"sess-{self._session_index}"}

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        self.run_states[run_id] = {"run_id": run_id, "output_text": self.default_output_text.format(text=text)}
        return {"run_id": run_id}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace, title="Agent A"),)


def test_group_message_without_mention_is_ignored(tmp_path: Path) -> None:
    """Unmentioned group traffic must not invoke the kernel."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="web_relay",
        text="hello group",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={"mentioned_agent_ids": [], "trigger": "ambient"},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is None
    assert kernel.create_session_calls == []
    assert kernel.send_calls == []
    assert channel.sent == []


def test_group_message_with_mention_or_reply_runs(tmp_path: Path) -> None:
    """Mentioned or agent-reply group traffic must still reach the kernel."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    mentioned = InboundMessage(
        channel_name="web_relay",
        text="@agent-a hello",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={"mentioned_agent_ids": ["agent-a"], "trigger": "mention"},
    )
    replied = InboundMessage(
        channel_name="web_relay",
        text="follow-up",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={"reply_to_agent_id": "agent-a", "trigger": "reply"},
    )

    first = asyncio.run(pipeline.handle_inbound(mentioned))
    second = asyncio.run(pipeline.handle_inbound(replied))

    assert first is not None
    assert second is not None
    assert [call["text"] for call in kernel.send_calls] == ["@agent-a hello", "follow-up"]
    assert [item.text for item in channel.sent] == ["reply:@agent-a hello", "reply:follow-up"]


def test_group_message_with_mention_and_no_reply_token_stays_silent(tmp_path: Path) -> None:
    """Mentioned group traffic that returns NO_REPLY must stay silent."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernelClient()
    kernel.default_output_text = "NO_REPLY"
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="web_relay",
        text="@agent-a stay quiet",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={"mentioned_agent_ids": ["agent-a"], "trigger": "mention"},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
    assert kernel.send_calls == [{"session_id": "sess-1", "text": "@agent-a stay quiet", "run_id": "run-1"}]
    assert channel.sent == []


def test_local_channel_keeps_working_without_im_connection(tmp_path: Path) -> None:
    """Gateway local channel execution must not depend on IM websocket connectivity."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("qq")
    kernel = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="qq",
        text="offline still works",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.reply_text == "reply:offline still works"
    assert kernel.send_calls == [{"session_id": "sess-1", "text": "offline still works", "run_id": "run-1"}]
    assert channel.sent == [
        OutboundMessage(
            channel_name="qq",
            text="reply:offline still works",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
