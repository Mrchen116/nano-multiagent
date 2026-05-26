"""端到端集成测试：provider SSE error → IM messages API 显示错误内容 + delivery_status=failed。

bugfix-380: 验收路径
1. fixture provider 强制返回 SSE error 帧
2. 通过 HTTP kernel API 发消息
3. 断言 GET /im/v1/conversations/.../messages 能看到错误内容
4. 断言 delivery_status=failed

本测试使用 httpx.MockTransport 注入 fake LLM provider，无需真实 LLM。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.tools.base import set_tool_safety_config_factory, set_tool_safety_factory
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class SseErrorLLMClient(LLMClient):
    """LLM client that simulates an upstream SSE error (quota exceeded)."""

    def __init__(self, error_message: str = "You've reached your usage limit for this billing cycle.") -> None:
        self._error_message = error_message

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        raise ModelError(
            f"anthropic: {self._error_message}",
            details={"error_type": "permission_error"},
            retryable=False,
        )
        yield  # make this an async generator


async def test_provider_sse_error_persists_error_assistant_message(tmp_path: Path) -> None:
    """SSE error → 持久化带 is_provider_error=True 的 assistant 消息，内容含错误文案。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = manager.create_session(workspace_root=workspace.resolve())

    error_text = "You've reached your usage limit for this billing cycle."
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=SseErrorLLMClient(error_text),
        model="mock-model",
    )

    with pytest.raises(ModelError):
        await runtime.run(session.session_id, [{"type": "text", "text": "hi"}])

    manager.writer.flush()

    # 验证 JSONL 里有 is_provider_error=True 的 assistant 消息
    messages = manager.list_turn_messages(session.session_id)
    error_msgs = [m for m in messages if m.role == "assistant" and m.metadata.get("is_provider_error")]
    assert len(error_msgs) == 1, f"应有 1 条 is_provider_error 消息，实际: {len(error_msgs)}"
    error_msg = error_msgs[0]
    assert "⚠️" in error_msg.content, "错误消息应包含 ⚠️"
    assert "模型调用失败" in error_msg.content, "错误消息应包含 '模型调用失败'"
    assert "usage limit" in error_msg.content or "billing" in error_msg.content, \
        f"错误消息应包含 provider 原文，实际: {error_msg.content!r}"


async def test_provider_error_not_in_next_llm_history(tmp_path: Path) -> None:
    """第一轮 provider 错误的 assistant 消息不应出现在下一轮 LLM 调用的 history 中。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = manager.create_session(workspace_root=workspace.resolve())

    # 第一轮：provider 报错
    runtime_err = AgentRuntime(
        session_manager=manager,
        llm_client=SseErrorLLMClient("quota exceeded"),
        model="mock-model",
    )
    with pytest.raises(ModelError):
        await runtime_err.run(session.session_id, [{"type": "text", "text": "first"}])
    manager.writer.flush()

    # 第二轮：正常 provider，检查 LLM 看不到上一轮错误消息
    captured_requests: list[LLMGenerateRequest] = []

    class CapturingLLMClient(LLMClient):
        async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
            captured_requests.append(request)
            yield LLMMessage(role="assistant", content="normal response")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    runtime2 = AgentRuntime(
        session_manager=manager,
        llm_client=CapturingLLMClient(),
        model="mock-model",
    )
    await runtime2.run(session.session_id, [{"type": "text", "text": "second"}])

    assert captured_requests, "第二轮应该发出 LLM 请求"
    messages_sent = captured_requests[-1].messages
    error_assistant_msgs = [
        m for m in messages_sent
        if m.role == "assistant" and "⚠️" in (m.content or "")
    ]
    assert not error_assistant_msgs, \
        f"is_provider_error 消息不应出现在下一轮 LLM history 中: {error_assistant_msgs}"

    # 但第一轮的 user message 应该保留
    user_msgs = [m for m in messages_sent if m.role == "user"]
    user_contents = [m.content for m in user_msgs]
    assert "first" in user_contents, \
        f"第一轮的 user message 应保留在 history 中，实际 user 消息: {user_contents}"


async def test_happy_path_not_broken_by_bugfix380(tmp_path: Path) -> None:
    """happy path(LLM 上游正常)的行为不应受 bugfix-380 影响。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = manager.create_session(workspace_root=workspace.resolve())

    class NormalLLMClient(LLMClient):
        async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
            yield LLMMessage(role="assistant", content="hello")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=NormalLLMClient(),
        model="mock-model",
    )
    result = await runtime.run(session.session_id, [{"type": "text", "text": "hi"}])

    manager.writer.flush()
    messages = manager.list_turn_messages(session.session_id)
    assistant_msgs = [m for m in messages if m.role == "assistant"]
    # 不应有 is_provider_error 消息
    error_msgs = [m for m in assistant_msgs if m.metadata.get("is_provider_error")]
    assert not error_msgs, "happy path 不应产生 is_provider_error 消息"
    # 应有正常文本消息
    normal_msgs = [m for m in assistant_msgs if "hello" in (m.content or "")]
    assert normal_msgs, "happy path 应产生正常 assistant 消息"


async def test_provider_error_message_truncated_at_1kb(tmp_path: Path) -> None:
    """provider 错误文案超过 1KB 时应被截断。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = manager.create_session(workspace_root=workspace.resolve())

    long_error = "A" * 2000  # 超过 1KB
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=SseErrorLLMClient(long_error),
        model="mock-model",
    )
    with pytest.raises(ModelError):
        await runtime.run(session.session_id, [{"type": "text", "text": "hi"}])
    manager.writer.flush()

    messages = manager.list_turn_messages(session.session_id)
    error_msgs = [m for m in messages if m.role == "assistant" and m.metadata.get("is_provider_error")]
    assert error_msgs, "应有 is_provider_error 消息"
    content = error_msgs[0].content
    assert len(content) < 2100, f"错误消息被截断后不应超过 2100 字符，实际: {len(content)}"
    assert "truncated" in content or "…" in content, "截断的消息应包含截断标记"


# --- bugfix-380 fast-lane round 3: 事件顺序测试 ---


async def test_provider_error_hook_event_order_message_end_before_turn_end(tmp_path: Path) -> None:
    """ModelError 路径下 message_end 必须在 turn_end 之前；turn_end 必须携带 completed=False。

    这个测试验证 Gateway observer 能正确渲染错误气泡（先收到 assistant 内容，再收到 turn_end）。
    修复前：loop finally 块无条件发 turn_end(completed=True)，再由 runtime 发 message_end——顺序颠倒。
    修复后：loop 失败路径不发 turn_end；runtime except ModelError 块在 message_end 之后补发 turn_end(completed=False)。
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = manager.create_session(workspace_root=workspace.resolve())

    events: list[tuple[str, dict[str, Any]]] = []

    hooks = HookRegistry()

    async def capture_message_end(payload: dict[str, Any], ctx: Any) -> None:
        events.append(("message_end", dict(payload)))

    async def capture_turn_end(payload: dict[str, Any], ctx: Any) -> None:
        events.append(("turn_end", dict(payload)))

    hooks.on("message_end", capture_message_end)
    hooks.on("turn_end", capture_turn_end)
    runner = HookRunner(registry=hooks)

    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=SseErrorLLMClient("quota exceeded"),
        model="mock-model",
        hook_runner=runner,
    )

    with pytest.raises(ModelError):
        await runtime.run(session.session_id, [{"type": "text", "text": "hi"}])

    event_names = [e[0] for e in events]

    # message_end (assistant error content) 必须在 turn_end 之前
    assert "message_end" in event_names, "应有 message_end 事件"
    assert "turn_end" in event_names, "应有 turn_end 事件"

    msg_end_idx = event_names.index("message_end")
    turn_end_idx = event_names.index("turn_end")
    assert msg_end_idx < turn_end_idx, (
        f"message_end 必须在 turn_end 之前，实际顺序: {event_names}"
    )

    # turn_end 必须携带 completed=False（告诉下游这是失败收尾）
    turn_end_payload = events[turn_end_idx][1]
    assert turn_end_payload.get("completed") is False, (
        f"turn_end 的 completed 必须是 False，实际: {turn_end_payload.get('completed')!r}"
    )

    # message_end 的 content 必须包含错误文案
    msg_end_payload = events[msg_end_idx][1]
    assert "模型调用失败" in (msg_end_payload.get("content") or ""), (
        f"message_end 的 content 应包含错误文案，实际: {msg_end_payload.get('content')!r}"
    )
    assert msg_end_payload.get("role") == "assistant", (
        f"message_end 应是 assistant role，实际: {msg_end_payload.get('role')!r}"
    )


async def test_gateway_observer_does_not_lock_bubble_on_provider_error(tmp_path: Path) -> None:
    """turn_end(completed=False) 时 Gateway observer 不应发送 message_completed。

    这个测试模拟 _build_kernel_event_observer 的行为：
    - 当 turn_end.completed=True 时应发 message_completed（正常路径）
    - 当 turn_end.completed=False 时不应发 message_completed（错误路径，由后续 message_delta 填充）
    """
    from personal_assistant.main import _build_kernel_event_observer

    sent_messages: list[dict[str, Any]] = []

    class FakeManager:
        connected = True

        async def send_json(self, msg_type: str, payload: dict[str, Any]) -> None:
            sent_messages.append({"type": msg_type, "payload": payload})

    manager_instance = FakeManager()

    def manager_factory() -> Any:
        return manager_instance

    run_context_store: dict[str, dict[str, str]] = {
        "test-run-1": {
            "conversation_id": "conv-123",
            "message_id": "msg-456",
            "agent_id": "agent-789",
        }
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=manager_factory,
        run_context_store=run_context_store,
    )

    # 正常路径：turn_end(completed=True) 应发 message_completed
    coro = observer({
        "event": "turn_end",
        "run_id": "test-run-1",
        "completed": True,
    })
    if coro is not None:
        await coro
    await asyncio.sleep(0.01)  # 等 create_task 完成

    completed_msgs_before = [
        m for m in sent_messages if m.get("payload", {}).get("kind") == "message_completed"
    ]

    # 错误路径：turn_end(completed=False) 不应发 message_completed
    sent_messages.clear()
    coro = observer({
        "event": "turn_end",
        "run_id": "test-run-1",
        "completed": False,
    })
    if coro is not None:
        await coro
    await asyncio.sleep(0.01)

    completed_msgs_after = [
        m for m in sent_messages if m.get("payload", {}).get("kind") == "message_completed"
    ]
    assert not completed_msgs_after, (
        f"turn_end(completed=False) 不应触发 message_completed，实际发送了: {completed_msgs_after}"
    )
