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

    def submit_message(self, *, session_id, texts, image_urls=None, **_kwargs):
        self._run_count += 1
        run_id = f"run-{self._run_count}"
        self.send_calls.append({"session_id": session_id, "texts": texts, "run_id": run_id})
        return {"run_id": run_id, "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id, last_event_id=None):
        run_id = self.send_calls[-1]["run_id"] if self.send_calls else "run-1"
        yield {"event": "run_status", "run_id": run_id, "status": "completed", "output_text": "ok"}

    def get_run(self, *, run_id):
        return {"status": "completed", "output_text": "ok"}

    def get_session(self, *, session_id, **_kwargs):
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

    # drain returns (sender, text) tuples since M246
    assert any(text == "hello everyone" for _, text in drained_a), f"agent-a buffer missing message: {drained_a}"
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


def test_peer_agent_reply_relay_buffers_when_self_not_mentioned(tmp_path: Path) -> None:
    """Agent reply relays for non-mentioned peers should buffer and never execute.

    bugfix-358: IM fans out one group relay per peer agent on delivery_receipt; no
    background_context_only flag. Gateway decides trigger vs buffer from
    mentioned_agent_ids + group_reply_policy alone. When self is not in
    mentioned_agent_ids (MENTION policy default), pipeline buffers the message
    into group_context_store without allocating a run.
    """
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-a")

    peer_reply_for_a = InboundMessage(
        channel_name="web_relay",
        text="here is the answer",
        external_user_id="agent-b-user",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"source_agent_id": "agent-b", "mentioned_agent_ids": []},
    )
    later_for_a = InboundMessage(
        channel_name="web_relay",
        text="@agent-a continue",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    reply_result = asyncio.run(pipeline.handle_inbound(peer_reply_for_a))
    mention_result = asyncio.run(pipeline.handle_inbound(later_for_a))

    assert reply_result is None
    assert mention_result is not None
    assert mention_result.agent_id == "agent-a"
    # Since M246: each group message is prefixed with [sender_id] before being sent to the kernel.
    assert kernel.send_calls == [{"session_id": "sess-1", "texts": ["[agent-b-user] here is the answer", "[user-1] @agent-a continue"], "run_id": "run-1"}]

    buf_key_a = pipeline._group_buf_key_for_agent(peer_reply_for_a, "agent-a")
    assert store.drain(buf_key_a) == []


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

    # agent-b must have sent both the plain message and the mention as texts.
    # Since M246: each group message is prefixed with [sender_id] by the gateway layer.
    assert len(kernel.send_calls) == 1
    assert kernel.send_calls[0]["texts"] == ["[user-1] hello everyone", "[user-1] @agent-b what time is it?"]


def test_non_mentioned_group_relay_buffers_for_its_target_agent(tmp_path: Path) -> None:
    """Per-agent relays for other participants must buffer, not reroute back to the mentioned agent.

    This guards the real fan-out case:
    - user sends @agent-b in a group with agents a+b
    - IM creates one relay for agent-a and one relay for agent-b
    - agent-a's relay must buffer for agent-a instead of being re-routed to agent-b
    - on a later @agent-a turn, agent-a should drain that buffered @agent-b message as prior context
    """
    agents = _two_agents(tmp_path)
    pipeline, store, kernel = _build_pipeline(tmp_path, agents=agents, default_agent_id="agent-a")

    relay_for_a = InboundMessage(
        channel_name="web_relay",
        text="@agent-b first turn",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    relay_for_b = InboundMessage(
        channel_name="web_relay",
        text="@agent-b first turn",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    later_for_a = InboundMessage(
        channel_name="web_relay",
        text="@agent-a second turn",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    result_a_background = asyncio.run(pipeline.handle_inbound(relay_for_a))
    result_b = asyncio.run(pipeline.handle_inbound(relay_for_b))
    result_a = asyncio.run(pipeline.handle_inbound(later_for_a))

    assert result_a_background is None
    assert result_b is not None
    assert result_b.agent_id == "agent-b"
    assert result_a is not None
    assert result_a.agent_id == "agent-a"
    # Since M246: each group message is prefixed with [sender_id] by the gateway layer.
    assert len(kernel.send_calls) == 2
    assert kernel.send_calls[0]["texts"] == ["[user-1] @agent-b first turn"]
    assert kernel.send_calls[1]["texts"] == ["[user-1] @agent-b first turn", "[user-1] @agent-a second turn"]

    buf_key_a = pipeline._group_buf_key_for_agent(relay_for_a, "agent-a")
    assert store.drain(buf_key_a) == []
