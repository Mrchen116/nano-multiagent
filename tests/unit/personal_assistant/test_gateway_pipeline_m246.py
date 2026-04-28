"""M246 gateway pipeline tests: sender prefix formatting and buffer drain behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_pipeline import InboundPipeline, _format_sender_text
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list = []

    def start(self, on_inbound) -> None:
        pass

    def send(self, outbound) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        pass


class _FakeKernelClient:
    def __init__(self) -> None:
        self.send_calls: list[dict] = []
        self._session_count = 0
        self._run_count = 0

    def create_session(self, *, workspace_root, product_id, title, metadata):
        self._session_count += 1
        return {"session_id": f"sess-{self._session_count}"}

    def submit_message(self, *, session_id, texts, image_urls=None, priority="next"):
        self._run_count += 1
        run_id = f"run-{self._run_count}"
        self.send_calls.append({"session_id": session_id, "texts": texts, "run_id": run_id})
        return {"run_id": run_id, "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id, last_event_id=None):
        del session_id, last_event_id
        yield {"event": "assistant_message", "run_id": f"run-{self._run_count}", "content": "ok"}
        yield {"event": "run_status", "run_id": f"run-{self._run_count}", "status": "completed"}

    def get_run(self, *, run_id):
        return {"status": "completed", "output_text": "ok"}

    def get_session(self, *, session_id):
        return {"metadata": {"workspace_root": "/workspace"}}


def _build_pipeline(tmp_path: Path, *, with_store: bool = True) -> tuple[InboundPipeline, GroupContextStore | None, _FakeKernelClient]:
    dir_a = tmp_path / "agent-a"
    dir_a.mkdir()
    agents = (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=dir_a, title="Agent A"),)
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3") if with_store else None
    kernel = _FakeKernelClient()
    channel = _FakeChannel("web_relay")
    pipeline = InboundPipeline(
        kernel_client=kernel,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        group_context_store=store,
        default_agent_id="agent-a",
    )
    return pipeline, store, kernel


# ── _format_sender_text unit tests ────────────────────────────────────────────

def test_format_sender_text_with_non_empty_sender() -> None:
    """Non-empty sender produces [sender] text prefix."""
    result = _format_sender_text("user-1", "hello")
    assert result == "[user-1] hello"


def test_format_sender_text_with_empty_sender_returns_text_unchanged() -> None:
    """Empty sender string leaves text unchanged."""
    result = _format_sender_text("", "hello")
    assert result == "hello"


# ── Pipeline integration tests ────────────────────────────────────────────────

def test_group_mention_message_gets_sender_prefix(tmp_path: Path) -> None:
    """群聊 @mention 消息发送给 kernel 时带有 [external_user_id] 前缀。"""
    pipeline, _, kernel = _build_pipeline(tmp_path)

    msg = InboundMessage(
        channel_name="web_relay",
        text="@agent-a hello",
        external_user_id="alice",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    asyncio.run(pipeline.handle_inbound(msg))

    assert kernel.send_calls[0]["texts"] == ["[alice] @agent-a hello"]


def test_direct_message_has_no_sender_prefix(tmp_path: Path) -> None:
    """直聊消息不加前缀，texts 只含原始 text。"""
    pipeline, _, kernel = _build_pipeline(tmp_path, with_store=False)

    msg = InboundMessage(
        channel_name="web_relay",
        text="hello agent",
        external_user_id="alice",
        external_chat_id="conv-1",
        is_group=False,
        agent_id="agent-a",
        metadata={},
    )
    asyncio.run(pipeline.handle_inbound(msg))

    assert kernel.send_calls[0]["texts"] == ["hello agent"]


def test_buffer_drain_formats_sender_prefix_on_each_item(tmp_path: Path) -> None:
    """Buffer drain 后每条消息格式化为 [sender] text，作为独立 part。"""
    pipeline, store, kernel = _build_pipeline(tmp_path)

    plain = InboundMessage(
        channel_name="web_relay",
        text="first message",
        external_user_id="alice",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": []},
    )
    mention = InboundMessage(
        channel_name="web_relay",
        text="@agent-a respond",
        external_user_id="bob",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )

    asyncio.run(pipeline.handle_inbound(plain))
    asyncio.run(pipeline.handle_inbound(mention))

    assert kernel.send_calls[0]["texts"] == ["[alice] first message", "[bob] @agent-a respond"]


def test_no_buffer_single_group_text_has_prefix(tmp_path: Path) -> None:
    """单条群聊消息（无 buffer）仍有 [sender] 前缀，texts 长度为 1。"""
    pipeline, _, kernel = _build_pipeline(tmp_path)

    msg = InboundMessage(
        channel_name="web_relay",
        text="@agent-a ping",
        external_user_id="user-x",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    asyncio.run(pipeline.handle_inbound(msg))

    assert len(kernel.send_calls[0]["texts"]) == 1
    assert kernel.send_calls[0]["texts"][0] == "[user-x] @agent-a ping"


def test_multiple_buffered_items_become_independent_texts(tmp_path: Path) -> None:
    """多条 buffer 消息 + 当前 mention 各自作为独立 text，而非 join。"""
    pipeline, store, kernel = _build_pipeline(tmp_path)

    for sender, text in [("alice", "msg one"), ("bob", "msg two")]:
        asyncio.run(pipeline.handle_inbound(InboundMessage(
            channel_name="web_relay",
            text=text,
            external_user_id=sender,
            external_chat_id="conv-1",
            is_group=True,
            agent_id="agent-a",
            metadata={"mentioned_agent_ids": []},
        )))

    mention = InboundMessage(
        channel_name="web_relay",
        text="@agent-a go",
        external_user_id="charlie",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    asyncio.run(pipeline.handle_inbound(mention))

    texts = kernel.send_calls[0]["texts"]
    assert texts == ["[alice] msg one", "[bob] msg two", "[charlie] @agent-a go"]


# ---------------------------------------------------------------------------
# M247: sender_display_name replaces UUID in [sender] prefix
# ---------------------------------------------------------------------------


def test_group_mention_uses_display_name_when_provided(tmp_path: Path) -> None:
    """当 metadata 携带 sender_display_name 时，[sender] 前缀应使用 display_name 而非 UUID。"""
    pipeline, _, kernel = _build_pipeline(tmp_path)

    msg = InboundMessage(
        channel_name="web_relay",
        text="@agent-a hello",
        external_user_id="uuid-alice-raw",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"], "sender_display_name": "Alice Chen"},
    )
    asyncio.run(pipeline.handle_inbound(msg))

    assert kernel.send_calls[0]["texts"] == ["[Alice Chen] @agent-a hello"]


def test_group_mention_falls_back_to_uuid_when_no_display_name(tmp_path: Path) -> None:
    """metadata 无 sender_display_name 时 fallback 使用 external_user_id（UUID）。"""
    pipeline, _, kernel = _build_pipeline(tmp_path)

    msg = InboundMessage(
        channel_name="web_relay",
        text="@agent-a hello",
        external_user_id="uuid-alice-raw",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"]},
    )
    asyncio.run(pipeline.handle_inbound(msg))

    assert kernel.send_calls[0]["texts"] == ["[uuid-alice-raw] @agent-a hello"]


def test_buffered_messages_use_display_name_from_metadata(tmp_path: Path) -> None:
    """Buffer 中的消息以 sender_display_name 作为前缀（而非 UUID）。"""
    pipeline, store, kernel = _build_pipeline(tmp_path)

    # Buffer a message with display_name in metadata
    plain = InboundMessage(
        channel_name="web_relay",
        text="first message",
        external_user_id="uuid-bob-raw",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": [], "sender_display_name": "Bob Smith"},
    )
    # Trigger with display_name mention
    mention = InboundMessage(
        channel_name="web_relay",
        text="@agent-a respond",
        external_user_id="uuid-alice-raw",
        external_chat_id="conv-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"mentioned_agent_ids": ["agent-a"], "sender_display_name": "Alice Chen"},
    )

    asyncio.run(pipeline.handle_inbound(plain))
    asyncio.run(pipeline.handle_inbound(mention))

    texts = kernel.send_calls[0]["texts"]
    assert texts == ["[Bob Smith] first message", "[Alice Chen] @agent-a respond"]
