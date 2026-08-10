"""Independent Gateway group-trigger and local-autonomy coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeKernel


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound) -> None:  # noqa: ANN001
        self.on_inbound = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        return None


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=workspace, title="Agent A"
        ),
    )


def _pipeline(tmp_path: Path, channel: _FakeChannel, kernel: _FakeKernel):
    return build_inbound_pipeline(
        kernel=kernel,
        agents=_agents(tmp_path),
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        default_agent_id="agent-a",
    )


def test_group_reply_to_agent_runs_without_a_new_mention(tmp_path: Path) -> None:
    """Reply metadata independently addresses the agent in a group."""
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernel()
    pipeline = _pipeline(tmp_path, channel, kernel)
    inbound = InboundMessage(
        channel_name="web_relay",
        text="follow-up",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        metadata={"reply_to_agent_id": "agent-a", "trigger": "reply"},
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert kernel.send_calls[0]["texts"] == ["[user-1] follow-up"]
    assert [item.text for item in channel.sent] == ["reply:[user-1] follow-up"]


def test_local_channel_keeps_working_without_im_connection(tmp_path: Path) -> None:
    """Local channel execution does not depend on IM WebSocket connectivity."""
    channel = _FakeChannel("qq")
    kernel = _FakeKernel()
    pipeline = _pipeline(tmp_path, channel, kernel)
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
    assert kernel.send_calls == [
        {"session_id": "sess-1", "texts": ["offline still works"], "run_id": "run-1"}
    ]
    assert channel.sent == [
        OutboundMessage(
            channel_name="qq",
            text="reply:offline still works",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
