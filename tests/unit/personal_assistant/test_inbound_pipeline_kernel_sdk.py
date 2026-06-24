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
        model: str | None = None,
    ) -> MagicMock:
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.submit_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "origin": origin,
                "workspace_root": workspace_root,
                "model": model,
            }
        )
        record = MagicMock()
        record.run_id = run_id
        return record

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        message_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        workspace_root: Path | None = None,
    ) -> dict[str, Any]:
        """Record an out-of-band history append without spawning a run."""
        return {
            "session_id": session_id,
            "entry_id": "entry-1",
            "kind": "turn_appended",
            "created_at": "now",
            "turn_id": "",
            "role": role,
            "content": content,
        }

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
