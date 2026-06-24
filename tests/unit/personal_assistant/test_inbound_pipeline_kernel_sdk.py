"""M3: InboundPipeline 使用 Kernel SDK (agent.sdk) 替代 KernelApiClient。

这些测试验证 InboundPipeline 在使用进程内 Kernel SDK 后行为与原 HTTP 客户端版本等价。
C1 红测阶段：InboundPipeline 尚未接受 kernel 参数，这些测试应该失败。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

import pytest

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel


class _FakeSession:
    """Minimal session stub returned by Kernel.create_session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        # Simulate workspace metadata for _binding_matches_workspace_root
        self.workspace_root: str | None = None


class _FakeKernel:
    """Minimal Kernel SDK stub for pipeline tests.

    Mirrors the Kernel public API used by InboundPipeline:
      - create_session (async)
      - submit (sync, non-blocking)
      - stream (returns AsyncIterator)
      - interrupt (sync)
    """

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self._session_index = 0
        self._run_index = 0
        self._sessions: dict[str, _FakeSession] = {}
        # Test-controlled active run per kernel session. When set, a steer=True
        # submit injects into it (returns injected=True, reusing this run_id);
        # mirrors the real Kernel.submit(steer=True) atomic inject-or-new branch.
        self.active_run_by_session: dict[str, str] = {}

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: Path | None = None,
        skills: list[str] | None = None,
        tool_allowlist: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> _FakeSession:
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        session = _FakeSession(session_id)
        session.workspace_root = str(workspace_root) if workspace_root else None
        self.create_session_calls.append(
            {
                "title": title,
                "workspace_root": workspace_root,
                "skills": skills,
                "tool_allowlist": tool_allowlist,
                "metadata": metadata,
            }
        )
        self._sessions[session_id] = session
        return session

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: Any = None,
        workspace_root: Path | None = None,
        trace_id: str | None = None,
        steer: bool = False,
        flush_held: bool = True,
        model: str | None = None,
    ) -> MagicMock:
        active = self.active_run_by_session.get(session_id)
        if steer and active is not None:
            # Inject into the active run: no new run created, injected=True.
            self.submit_calls.append(
                {
                    "session_id": session_id,
                    "parts": parts,
                    "origin": origin,
                    "workspace_root": workspace_root,
                    "steer": True,
                    "injected": True,
                }
            )
            record = MagicMock()
            record.run_id = active
            record.injected = True
            return record
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.submit_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "origin": origin,
                "workspace_root": workspace_root,
                "steer": steer,
                "injected": False,
                "model": model,
            }
        )
        record = MagicMock()
        record.run_id = run_id
        record.injected = False
        return record

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        # Derive the last run_id for this session from submit_calls.
        last_run_id = None
        for call in reversed(self.submit_calls):
            if call["session_id"] == session_id:
                # run_id was assigned during submit; re-derive it by counting earlier calls
                idx = self.submit_calls.index(call)
                last_run_id = f"run-{idx + 1}"
                break

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            if last_run_id:
                text = "reply from sdk kernel"
                yield {
                    "event": "assistant_message",
                    "run_id": last_run_id,
                    "content": text,
                }
                yield {
                    "event": "run_status",
                    "run_id": last_run_id,
                    "status": "completed",
                }

        return _gen()

    def interrupt(self, session_id: str) -> str | None:
        return None

    def close(self) -> None:
        pass

    def get_session(
        self, session_id: str, *, workspace_root: str | None = None
    ) -> dict[str, Any]:
        """Return session payload mirroring real Kernel.get_session contract.

        workspace_root is exposed as a top-level key (not inside metadata) to
        match the Kernel.get_session contract fixed in refactor-387.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"session not found: {session_id}")
        return {
            "session_id": session_id,
            "status": "active",
            "workspace_root": session.workspace_root or "",
            "metadata": {},
        }


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_a.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=agent_a, title="Agent A"
        ),
    )


def test_inbound_pipeline_accepts_kernel_sdk_and_routes_message(tmp_path: Path) -> None:
    """M3: InboundPipeline 接受 kernel= 参数（Kernel SDK），处理入站消息后能回复。"""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()

    # M3 后 InboundPipeline 接受 kernel 而非 kernel_client
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    pipeline = InboundPipeline(
        kernel=kernel,  # <-- M3 新参数
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello sdk",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.agent_id == "agent-a"
    assert result.session_key == "web:chat-1:agent-a"
    # kernel.create_session was called once
    assert len(kernel.create_session_calls) == 1
    assert kernel.create_session_calls[0]["workspace_root"] == agents[0].workspace_root
    # kernel.submit was called once
    assert len(kernel.submit_calls) == 1
    assert kernel.submit_calls[0]["session_id"] == result.kernel_session_id
    # Channel received a reply
    assert len(channel.sent) == 1
    assert channel.sent[0].target_chat_id == "chat-1"


def test_inbound_pipeline_submits_agent_selected_model(tmp_path: Path) -> None:
    """bugfix-429 R3: an agent's default_model is passed to kernel.submit per turn."""
    agent_dir = tmp_path / "gpt-agent"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="gpt-agent",
            workspace_root=agent_dir,
            title="GPT Agent",
            default_model="codex_oauth:gpt-5.5",
        ),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="gpt-agent",
        product_default_model="kimiCoding:K2.6",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hi",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    assert kernel.submit_calls[0]["model"] == "codex_oauth:gpt-5.5"


def test_inbound_pipeline_falls_back_to_product_default_model(tmp_path: Path) -> None:
    """bugfix-429 R3: agent without a selected model uses the product default."""
    agents = _agents(tmp_path)  # agent-a has no default_model
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        product_default_model="kimiCoding:K2.6",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hi",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    assert kernel.submit_calls[0]["model"] == "kimiCoding:K2.6"


def test_inbound_pipeline_kernel_sdk_stop_command_interrupts(tmp_path: Path) -> None:
    """M3: /stop 命令通过 kernel.interrupt 而非 kernel_client.interrupt_session 打断运行。"""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()

    interrupt_calls: list[str] = []
    original_interrupt = kernel.interrupt

    def _recording_interrupt(session_id: str) -> str | None:
        interrupt_calls.append(session_id)
        return original_interrupt(session_id)

    kernel.interrupt = _recording_interrupt  # type: ignore[method-assign]

    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    # First send a normal message to get an active session
    inbound = InboundMessage(
        channel_name="web",
        text="do something",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    asyncio.run(pipeline.handle_inbound(inbound))

    # Inject an "active" run so /stop has something to interrupt
    session_key = "web:chat-1:agent-a"
    binding = pipeline._session_store.get(session_key)
    if binding:
        pipeline._active_runs[session_key] = "run-1"  # noqa: SLF001

    stop_msg = InboundMessage(
        channel_name="web",
        text="/stop",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    result = asyncio.run(pipeline.handle_inbound(stop_msg))

    assert result is not None
    # /stop should have called kernel.interrupt
    assert len(interrupt_calls) >= 1


def test_inbound_pipeline_kernel_sdk_stream_delivers_events(tmp_path: Path) -> None:
    """M3: pipeline 通过 kernel.stream 消费事件，正确提取 reply_text。"""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()

    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="stream me",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    # reply_text comes from the assistant_message event yielded by kernel.stream
    assert result.reply_text == "reply from sdk kernel"
    assert channel.sent[0].text == "reply from sdk kernel"


# ---------------------------------------------------------------------------
# bugfix-426-M1 R3: mid-run steering — inbound message during an active run is
# injected into it (steer=True), not queued behind it.
# ---------------------------------------------------------------------------


def _group_agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_a.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=agent_a,
            title="Agent A",
            group_reply_policy="ALWAYS",
        ),
    )


def _make_pipeline(kernel, agents, tmp_path):  # noqa: ANN001, ANN201
    from personal_assistant.gateway.group_context_store import GroupContextStore
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline

    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        group_context_store=GroupContextStore(db_path=tmp_path / "group_ctx.sqlite3"),
    )
    return pipeline, channel


def test_steer_injects_into_active_run_not_new_run(tmp_path: Path) -> None:
    """A direct-chat message arriving while a run is active is steered into it:
    submit(steer=True) returns injected=True, no new run is queued."""
    kernel = _FakeKernel()
    pipeline, _channel = _make_pipeline(kernel, _agents(tmp_path), tmp_path)

    # First message creates the session + binding (and finishes via the fast stub).
    first = InboundMessage(
        channel_name="web",
        text="run a long task",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    asyncio.run(pipeline.handle_inbound(first))
    session_key = "web:chat-1:agent-a"
    binding = pipeline._session_store.get(session_key)  # noqa: SLF001
    assert binding is not None
    kernel_session_id = binding.kernel_session_id

    # Simulate an active run for that session (both the gateway gate and the
    # kernel's own active-run map the steer submit consults).
    pipeline._active_runs[session_key] = "run-active"  # noqa: SLF001
    kernel.active_run_by_session[kernel_session_id] = "run-active"

    submits_before = len(kernel.submit_calls)
    steer_msg = InboundMessage(
        channel_name="web",
        text="actually use web_search",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    result = asyncio.run(pipeline.handle_inbound(steer_msg))

    # Exactly one new submit, and it was a steer injection (not a new run).
    assert len(kernel.submit_calls) == submits_before + 1
    steer_call = kernel.submit_calls[-1]
    assert steer_call["steer"] is True
    assert steer_call["injected"] is True
    assert steer_call["session_id"] == kernel_session_id
    # The injected message text is carried in parts.
    assert any(
        p.get("type") == "text" and "actually use web_search" in p.get("text", "")
        for p in steer_call["parts"]
    )
    assert result is not None
    assert result.run_id == "run-active"


def test_idle_message_opens_new_run_not_steer(tmp_path: Path) -> None:
    """With no active run, a message is a normal new run (steer degrades): the
    submit is not an injection."""
    kernel = _FakeKernel()
    pipeline, _channel = _make_pipeline(kernel, _agents(tmp_path), tmp_path)

    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    asyncio.run(pipeline.handle_inbound(inbound))

    assert len(kernel.submit_calls) == 1
    assert kernel.submit_calls[0]["injected"] is False


def test_group_steer_preserves_sender_prefix_and_buffered_context(
    tmp_path: Path,
) -> None:
    """A group-chat steer reuses the same parts builder as the normal path:
    the steered message carries the sender prefix and any buffered context from
    other speakers — not a bare message.text."""
    kernel = _FakeKernel()
    pipeline, _channel = _make_pipeline(kernel, _group_agents(tmp_path), tmp_path)

    # First group message creates the session binding.
    first = InboundMessage(
        channel_name="web",
        text="@agent-a kick off",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"sender_display_name": "Alice"},
    )
    asyncio.run(pipeline.handle_inbound(first))
    session_key = "web:grp-1:agent-a"
    binding = pipeline._session_store.get(session_key)  # noqa: SLF001
    assert binding is not None
    kernel_session_id = binding.kernel_session_id

    # Buffer a message from another speaker (not addressed to agent-a) so the
    # next turn must drain it into context.
    buf_key = pipeline._group_buf_key_for_agent(first, "agent-a")  # noqa: SLF001
    pipeline._group_context_store.append(buf_key, "context from bob", sender="Bob")  # noqa: SLF001

    # Active run → the new group message must steer into it.
    pipeline._active_runs[session_key] = "run-active"  # noqa: SLF001
    kernel.active_run_by_session[kernel_session_id] = "run-active"

    steer_msg = InboundMessage(
        channel_name="web",
        text="@agent-a change direction",
        external_user_id="user-2",
        external_chat_id="grp-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"sender_display_name": "Carol"},
    )
    asyncio.run(pipeline.handle_inbound(steer_msg))

    steer_call = kernel.submit_calls[-1]
    assert steer_call["steer"] is True and steer_call["injected"] is True
    texts = [p.get("text", "") for p in steer_call["parts"] if p.get("type") == "text"]
    joined = "\n".join(texts)
    # Buffered other-speaker context is drained in with its sender prefix.
    assert "[Bob] context from bob" in joined
    # The current speaker's message keeps the sender prefix (not bare text).
    assert "[Carol] @agent-a change direction" in joined


# ---------------------------------------------------------------------------
# bugfix-426-M3: concurrent steer must not race the group-buffer drain.
# Two inbound messages for the same session both pass the has_active_run gate
# and enter the steer fast-path. The "has_active_run check → drain" span must
# stay serial per session so a second steer cannot drain (destructive) while a
# first steer is mid-decision — otherwise the buffered group context is split
# between the two (one drains everything, the other drains nothing), violating
# the gateway invariant "群聊运行中 steer 保留发言人与缓冲上下文".
# ---------------------------------------------------------------------------


def test_concurrent_group_steer_drain_is_serial_not_interleaved(
    tmp_path: Path,
) -> None:
    """Two concurrent group steers must not interleave their buffer drains.

    Each steer's ``[has_active_run gate] → _build_message_parts(drain)`` span is
    serialized per session. We instrument the drain entry and inject a yield
    point right after binding (mirroring the real ``await _ensure_binding`` yield
    that lets a second coroutine cut in). With serialization the recorded order
    is ``[A bind, A drain, B bind, B drain]`` — each coroutine's bind and drain
    are adjacent. Without it the order interleaves (``[A bind, B bind, ...]``),
    proving a second coroutine drained while the first was still mid-decision.
    """
    kernel = _FakeKernel()
    pipeline, _channel = _make_pipeline(kernel, _group_agents(tmp_path), tmp_path)

    # First group message creates the session binding and an active run.
    first = InboundMessage(
        channel_name="web",
        text="@agent-a kick off",
        external_user_id="user-1",
        external_chat_id="grp-1",
        is_group=True,
        agent_id="agent-a",
        metadata={"sender_display_name": "Alice"},
    )
    asyncio.run(pipeline.handle_inbound(first))
    session_key = "web:grp-1:agent-a"
    binding = pipeline._session_store.get(session_key)  # noqa: SLF001
    assert binding is not None
    kernel_session_id = binding.kernel_session_id

    # Buffer other-speaker context so both steers contend for the same drain.
    buf_key = pipeline._group_buf_key_for_agent(first, "agent-a")  # noqa: SLF001
    pipeline._group_context_store.append(buf_key, "ctx from bob", sender="Bob")  # noqa: SLF001

    # Active run → both new group messages steer into it.
    pipeline._active_runs[session_key] = "run-active"  # noqa: SLF001
    kernel.active_run_by_session[kernel_session_id] = "run-active"

    events: list[str] = []

    # Derive the acting coroutine's label from the message text itself (the "A"
    # / "B" tag is embedded), NOT a shared variable — a shared label races across
    # the await points and misattributes events.
    def _label_of(message: InboundMessage) -> str:
        return "A" if "first steer" in message.text else "B"

    # Record drain entry per coroutine by wrapping _build_message_parts (the
    # destructive drain call site), keyed by the message being built.
    real_build = pipeline._build_message_parts  # noqa: SLF001

    def _instrumented_build(message, *, agent_id, sender_label):  # noqa: ANN001, ANN202
        events.append(f"drain:{_label_of(message)}")
        return real_build(message, agent_id=agent_id, sender_label=sender_label)

    pipeline._build_message_parts = _instrumented_build  # type: ignore[method-assign]  # noqa: SLF001

    # Wrap _ensure_binding to record the bind step and yield control afterwards,
    # opening the exact interleaving window the real await creates.
    real_ensure = pipeline._ensure_binding  # noqa: SLF001

    async def _instrumented_ensure(message, *, agent_id, session_key):  # noqa: ANN001, ANN202
        binding_ = await real_ensure(
            message, agent_id=agent_id, session_key=session_key
        )
        events.append(f"bind:{_label_of(message)}")
        await asyncio.sleep(0)
        return binding_

    pipeline._ensure_binding = _instrumented_ensure  # type: ignore[method-assign]  # noqa: SLF001

    async def _drive() -> None:
        async def _one(sender: str, text: str) -> None:
            await pipeline.handle_inbound(
                InboundMessage(
                    channel_name="web",
                    text=text,
                    external_user_id=f"user-{sender}",
                    external_chat_id="grp-1",
                    is_group=True,
                    agent_id="agent-a",
                    metadata={"sender_display_name": sender},
                )
            )

        await asyncio.gather(
            _one("Carol", "@agent-a first steer"),
            _one("Dave", "@agent-a second steer"),
        )

    asyncio.run(_drive())

    # Each coroutine's bind and drain must be adjacent (serial), never split by
    # the other coroutine's drain. Find each drain's index and assert the bind
    # of the SAME label immediately precedes it with no foreign drain between.
    # Concretely: a serial schedule never produces two consecutive bind events.
    bind_positions = [i for i, e in enumerate(events) if e.startswith("bind:")]
    # Serial: binds are separated by that coroutine's own drain, so no two bind
    # events are adjacent. Interleaved race: "bind:A","bind:B" appear adjacent.
    for i, j in zip(bind_positions, bind_positions[1:]):
        between = events[i + 1 : j]
        assert any(e.startswith("drain:") for e in between), (
            f"two binds with no drain between them — drain raced: {events}"
        )
