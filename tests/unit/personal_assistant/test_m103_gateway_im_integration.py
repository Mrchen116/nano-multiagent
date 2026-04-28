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
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self.default_output_text = "reply:{text}"
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
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title, "metadata": metadata}
        )
        return {"session_id": f"sess-{self._session_index}"}

    def submit_message(self, *, session_id: str, texts: list[str], image_urls=None):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "texts": texts, "run_id": run_id})
        self.run_states[run_id] = {"run_id": run_id, "output_text": self.default_output_text.format(text=texts[-1] if texts else "")}
        return {"run_id": run_id, "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id, last_event_id=None):
        run_id = list(self.run_states.keys())[-1] if self.run_states else "run-1"
        yield {"event": "assistant_message", "run_id": run_id, "content": self.run_states.get(run_id, {}).get("output_text", "")}
        yield {"event": "run_status", "run_id": run_id, "status": "completed", "output_text": self.run_states.get(run_id, {}).get("output_text", "")}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace, title="Agent A"),)


def _two_agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    wa = tmp_path / "agent-a"
    wb = tmp_path / "agent-b"
    wa.mkdir()
    wb.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=wa, title="Agent A"),
        AgentWorkspaceConfig(agent_id="agent-b", workspace_root=wb, title="Agent B"),
    )


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
    # Since M246: group messages are prefixed with [sender_id] by the gateway layer.
    assert [call["texts"][-1] for call in kernel.send_calls] == ["[user-1] @agent-a hello", "[user-1] follow-up"]
    assert [item.text for item in channel.sent] == ["reply:[user-1] @agent-a hello", "reply:[user-1] follow-up"]


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
    # Since M246: group messages are prefixed with [sender_id] by the gateway layer.
    assert kernel.send_calls == [{"session_id": "sess-1", "texts": ["[user-1] @agent-a stay quiet"], "run_id": "run-1"}]
    assert channel.sent == []


def test_register_agent_refresh_drops_old_session_binding_and_recreates_session(tmp_path: Path) -> None:
    """Refreshing one agent config must force later messages onto a new kernel session."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernelClient()
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="web_relay",
        text="first turn",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
    )
    refreshed_workspace = tmp_path / "agent-a-v2"
    refreshed_workspace.mkdir()

    first = asyncio.run(pipeline.handle_inbound(inbound))
    pipeline.register_agent(
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=refreshed_workspace, title="Agent A v2")
    )
    session_store.drop_agent("agent-a")
    second = asyncio.run(pipeline.handle_inbound(inbound))

    assert first is not None
    assert second is not None
    assert [call["session_id"] for call in kernel.send_calls] == ["sess-1", "sess-2"]
    assert [call["workspace_root"] for call in kernel.create_session_calls] == [
        str(tmp_path / "agent-a"),
        str(refreshed_workspace),
    ]



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
    assert kernel.send_calls == [{"session_id": "sess-1", "texts": ["offline still works"], "run_id": "run-1"}]
    assert channel.sent == [
        OutboundMessage(
            channel_name="qq",
            text="reply:offline still works",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]


def test_group_multiagent_fanout_buffers_and_contextualises(tmp_path: Path) -> None:
    """Each agent's relay buffers messages into its own context; no cross-agent fan-out.

    After M231 the IM service sends one relay per participant agent.  Each gateway
    only buffers context for its own agent_id and drains it on the next addressed turn.
    The test simulates the relay-per-agent flow using explicit agent_id on each message.
    """
    from personal_assistant.gateway.group_context_store import GroupContextStore

    agents = _two_agents(tmp_path)
    channel = _FakeChannel("web_relay")
    kernel = _FakeKernelClient()
    store = GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3")
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        group_context_store=store,
        default_agent_id="agent-a",
    )

    # Step 1a: plain message relay targeted to agent-b → agent-b buffers, does not respond.
    plain_for_b = InboundMessage(
        channel_name="web_relay",
        text="hello everyone",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",  # relay explicitly targets agent-b
        metadata={"mentioned_agent_ids": []},
    )
    result_plain = asyncio.run(pipeline.handle_inbound(plain_for_b))
    assert result_plain is None
    assert kernel.send_calls == []

    # Step 2: @agent-b relay targeted to agent-b → agent-b drains its buffer then processes.
    mention_b = InboundMessage(
        channel_name="web_relay",
        text="@agent-b what time is it?",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-b",  # relay explicitly targets agent-b
        metadata={"mentioned_agent_ids": ["agent-b"]},
    )
    result_b = asyncio.run(pipeline.handle_inbound(mention_b))
    assert result_b is not None
    assert result_b.agent_id == "agent-b"
    assert len(kernel.send_calls) == 1
    # Since M246: group messages are prefixed with [sender_id] by the gateway layer.
    # agent-b must drain "hello everyone" then receive the @mention in its own buffer
    assert kernel.send_calls[0]["texts"] == ["[user-1] hello everyone", "[user-1] @agent-b what time is it?"]

    # Step 3a: plain message relay targeted to agent-a → agent-a buffers.
    plain_for_a = InboundMessage(
        channel_name="web_relay",
        text="hello everyone",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": []},
    )
    asyncio.run(pipeline.handle_inbound(plain_for_a))

    # Step 3b: @agent-a relay targeted to agent-a → agent-a drains its own buffer and processes.
    mention_a = InboundMessage(
        channel_name="web_relay",
        text="@agent-a your turn",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    result_a = asyncio.run(pipeline.handle_inbound(mention_a))
    assert result_a is not None
    assert result_a.agent_id == "agent-a"
    assert len(kernel.send_calls) == 2
    sent_texts = kernel.send_calls[1]["texts"]
    # Since M246: group messages are prefixed with [sender_id] by the gateway layer.
    # agent-a drains its own buffer ("hello everyone") then receives the @mention
    assert sent_texts[0] == "[user-1] hello everyone"
    assert sent_texts[-1] == "[user-1] @agent-a your turn"
