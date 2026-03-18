"""R3 regression guard: inbound_pipeline must NOT fan-out context to other agents' buffers.

After M231, each gateway only sees its own relay, so the buffer for non-target agents
must NOT be populated from a single relay.  Only the relay's own agent_id is buffered.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound) -> None:
        pass

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        pass


class _FakeKernelClient:
    def __init__(self) -> None:
        self.create_session_calls: list[dict] = []
        self.send_calls: list[dict] = []
        self._session_count = 0
        self._run_count = 0

    def create_session(self, *, workspace_root, product_id, title, metadata):
        self._session_count += 1
        sid = f"sess-{self._session_count}"
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title, "metadata": metadata}
        )
        return {"session_id": sid}

    def send_message_async(self, *, session_id, texts):
        self._run_count += 1
        run_id = f"run-{self._run_count}"
        self.send_calls.append({"session_id": session_id, "texts": texts, "run_id": run_id})
        return {"run_id": run_id}

    def get_run(self, *, run_id):
        return {"status": "completed", "output_text": "ok"}

    def get_session(self, *, session_id):
        return {"metadata": {"workspace_root": "/workspace"}}


def _two_agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    dir_a = tmp_path / "agent-a"
    dir_a.mkdir()
    dir_b = tmp_path / "agent-b"
    dir_b.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=dir_a, title="Agent A"),
        AgentWorkspaceConfig(agent_id="agent-b", workspace_root=dir_b, title="Agent B"),
    )


def _build_pipeline(
    tmp_path: Path,
    *,
    agents: tuple[AgentWorkspaceConfig, ...] | None = None,
    default_agent_id: str = "agent-a",
) -> tuple[InboundPipeline, GroupContextStore, _FakeKernelClient]:
    agents = agents or _two_agents(tmp_path)
    store = GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3")
    kernel = _FakeKernelClient()
    channel = _FakeChannel("web_relay")
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        group_context_store=store,
        default_agent_id=default_agent_id,
    )
    return pipeline, store, kernel


def test_no_mention_message_buffers_only_for_current_agent(tmp_path: Path) -> None:
    """群聊无 @ 消息时，只在本 relay 的 agent_id 缓冲区中追加，不广播到其他 agent。

    After fan-out removal, a relay for agent-a must only write to agent-a's buffer key,
    not to agent-b's buffer key.
    """
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-a")

    plain = InboundMessage(
        channel_name="web_relay",
        text="hello everyone",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",  # This relay is targeted to agent-a
        metadata={"mentioned_agent_ids": []},
    )
    result = asyncio.run(pipeline.handle_inbound(plain))

    assert result is None  # no mention → no processing

    buf_key_a = pipeline._group_buf_key_for_agent(plain, "agent-a")
    buf_key_b = pipeline._group_buf_key_for_agent(plain, "agent-b")

    # agent-a's buffer should contain the message (buffered for own future context)
    drained_a = store.drain(buf_key_a)
    # agent-b's buffer must NOT be populated by agent-a's relay
    drained_b = store.drain(buf_key_b)

    assert "hello everyone" in drained_a, f"agent-a buffer missing message: {drained_a}"
    assert drained_b == [], f"agent-b buffer must not be populated by agent-a's relay, got: {drained_b}"


def test_mention_message_does_not_broadcast_to_non_target_agent_buffer(tmp_path: Path) -> None:
    """群聊 @agent-b 消息时，agent-a 的 relay 只缓冲到自己的 buffer，不写入 agent-b 的 buffer。

    The @agent-b mention relay targets agent-b (should_process=True).
    After fan-out removal, the pipeline must NOT append to agent-a's buffer key.
    """
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-a")

    mention_b = InboundMessage(
        channel_name="web_relay",
        text="@agent-b what time is it?",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",  # This relay is targeted to agent-b
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    result = asyncio.run(pipeline.handle_inbound(mention_b))

    assert result is not None
    assert result.agent_id == "agent-b"

    buf_key_a = pipeline._group_buf_key_for_agent(mention_b, "agent-a")
    # After fan-out removal: agent-a's buffer must NOT contain the @agent-b message
    drained_a = store.drain(buf_key_a)
    assert drained_a == [], f"agent-a buffer must not receive @agent-b relay's message, got: {drained_a}"


def test_agent_reply_does_not_broadcast_to_other_agent_buffer(tmp_path: Path) -> None:
    """Agent-b 的回复不应写入 agent-a 的缓冲区（移除回复广播 loop）。"""
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-a")

    mention_b = InboundMessage(
        channel_name="web_relay",
        text="@agent-b reply now",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    asyncio.run(pipeline.handle_inbound(mention_b))

    buf_key_a = pipeline._group_buf_key_for_agent(mention_b, "agent-a")
    # The reply from agent-b must NOT appear in agent-a's buffer
    drained_a = store.drain(buf_key_a)
    # After fan-out removal, no reply broadcast → agent-a's buffer is empty
    agent_b_replies = [entry for entry in drained_a if "agent-b:" in entry]
    assert agent_b_replies == [], (
        f"agent-b reply must not be written to agent-a buffer, got: {agent_b_replies}"
    )


def test_own_agent_buffer_drain_still_works(tmp_path: Path) -> None:
    """Buffer drain for the target agent still works after fan-out removal.

    When agent-b's relay arrives with a plain message followed by a mention,
    agent-b must still drain its own buffer before processing the mention.
    """
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-b")

    # Step 1: plain message relay for agent-b → should_process=False, buffers for agent-b
    plain = InboundMessage(
        channel_name="web_relay",
        text="hello everyone",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",
        metadata={"mentioned_agent_ids": []},
    )
    r1 = asyncio.run(pipeline.handle_inbound(plain))
    assert r1 is None

    # Step 2: @agent-b relay → should_process=True, drains agent-b's buffer then processes
    mention_b = InboundMessage(
        channel_name="web_relay",
        text="@agent-b what time is it?",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    r2 = asyncio.run(pipeline.handle_inbound(mention_b))
    assert r2 is not None
    assert r2.agent_id == "agent-b"

    # agent-b must have sent both the plain message and the mention as texts
    assert len(kernel.send_calls) == 1
    assert kernel.send_calls[0]["texts"] == ["hello everyone", "@agent-b what time is it?"]
