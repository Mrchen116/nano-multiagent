"""Unit tests for realtime_stream hook event schemas (feat-338)."""

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.platform.hooks.builtins.realtime_stream import setup as setup_realtime_stream


class _FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def __call__(self, event: str, data: dict[str, object]) -> None:
        self.events.append({"event": event, "data": data})


def _make_ctx(publisher: _FakePublisher | None = None) -> HookContext:
    return HookContext(
        session_id="sess_1",
        turn_id="turn_1",
        metadata={"run_id": "run_1"},
        session_event_publisher=publisher,
    )


async def test_message_end_emits_assistant_message() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    diagnostics = await runner.dispatch_observe(
        "message_end",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "message_id": "msg_1",
            "role": "assistant",
            "content": "Hello world",
            "run_id": "run_1",
        },
        ctx,
    )
    assert all(d.status == "ok" for d in diagnostics)
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["event"] == "assistant_message"
    assert evt["data"]["event"] == "assistant_message"
    assert evt["data"]["content"] == "Hello world"
    assert evt["data"]["run_id"] == "run_1"


async def test_message_end_skips_non_assistant() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    await runner.dispatch_observe(
        "message_end",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "message_id": "msg_1",
            "role": "user",
            "content": "Hi",
            "run_id": "run_1",
        },
        ctx,
    )
    assert len(pub.events) == 0


async def test_tool_call_emits_tool_start_with_presentation() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    diagnostics = await runner.dispatch_observe(
        "tool_call",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "call_id": "call_1",
            "name": "read",
            "arguments": {"path": "src/app.py"},
            "run_id": "run_1",
        },
        ctx,
    )
    assert all(d.status == "ok" for d in diagnostics)
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["event"] == "tool_start"
    assert evt["data"]["event"] == "tool_start"
    assert evt["data"]["name"] == "read"
    assert "presentation" in evt["data"]
    assert evt["data"]["presentation"]["visible"] is True


async def test_tool_result_emits_tool_end_with_presentation() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    # The kernel emits the tool_result payload with key ``args`` (registry.py);
    # feat-409 fix 2: realtime_stream must surface it as ``arguments`` so the tool_end
    # event carries the real input (not {}) — otherwise the completed upsert clobbers
    # the running entry's input downstream.
    diagnostics = await runner.dispatch_observe(
        "tool_result",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "call_id": "call_1",
            "name": "read",
            "args": {"path": "src/app.py"},
            "arguments": {"path": "src/app.py"},
            "output": {"total_lines": 120},
            "duration_ms": 12,
            "run_id": "run_1",
        },
        ctx,
    )
    assert all(d.status == "ok" for d in diagnostics)
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["event"] == "tool_end"
    assert evt["data"]["event"] == "tool_end"
    assert evt["data"]["status"] == "completed"
    assert evt["data"]["duration_ms"] == 12
    assert evt["data"]["arguments"] == {"path": "src/app.py"}
    assert "presentation" in evt["data"]
    assert evt["data"]["presentation"]["visible"] is True


async def test_tool_result_failed_emits_tool_end_failed() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    await runner.dispatch_observe(
        "tool_result",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "call_id": "call_1",
            "name": "bash",
            "arguments": {"command": "exit 1"},
            "error": "Command exited with code 1",
            "duration_ms": 5,
            "run_id": "run_1",
        },
        ctx,
    )
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["data"]["status"] == "failed"
    assert evt["data"]["error"] == "Command exited with code 1"


async def test_tool_result_emits_tool_end_with_approval() -> None:
    # feat-434-M1: approval 随 tool_end 一并带出（与 reason_code 同款透传），让前端闸门
    # 区能读 tool_call.approval 显示「已授权 / 已拒绝」。
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    await runner.dispatch_observe(
        "tool_result",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "call_id": "call_1",
            "name": "bash",
            "arguments": {"command": "npm run build"},
            "output": {"ok": True},
            "duration_ms": 12,
            "approval": "user_allow",
            "run_id": "run_1",
        },
        ctx,
    )
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["data"]["event"] == "tool_end"
    assert evt["data"]["approval"] == "user_allow"


def test_presentation_dict_serializes_emoji() -> None:
    # feat-425 决策 1: _presentation_dict 把 event 的 emoji 序列化进 SSE,让自带
    # emoji 的工具(如 web_fetch=🌐)的图标随事件全程透传,而非靠前端名表。
    from agent.core.tools.presentation import ToolPresentationEvent
    from agent.platform.hooks.builtins.realtime_stream import _presentation_dict

    payload = _presentation_dict(
        ToolPresentationEvent(
            visible=True, label="Web", summary="https://x", emoji="🌐"
        )
    )
    assert payload["emoji"] == "🌐"
    assert payload["summary"] == "https://x"


def test_presentation_dict_none_has_empty_emoji() -> None:
    # 无 presentation 时 emoji 缺省空串,前端按名表兜底。
    from agent.platform.hooks.builtins.realtime_stream import _presentation_dict

    payload = _presentation_dict(None)
    assert payload["emoji"] == ""


async def test_pending_injection_consumed_emits_injection_consumed() -> None:
    """bugfix-426-M4 决策6: the loop's pending_injection_consumed observe event is
    forwarded as an ``injection_consumed`` session event carrying the run_id, so the
    gateway can roll the IM bubble at the steer's consume point."""
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(publisher=pub)

    diagnostics = await runner.dispatch_observe(
        "pending_injection_consumed",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "run_id": "run_1",
            "message_count": 1,
        },
        ctx,
    )
    assert all(d.status == "ok" for d in diagnostics)
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["event"] == "injection_consumed"
    assert evt["data"]["event"] == "injection_consumed"
    assert evt["data"]["run_id"] == "run_1"


async def test_pending_injection_consumed_without_run_id_is_skipped() -> None:
    """No run_id → nothing to scope the bubble roll to; emit nothing."""
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = HookContext(
        session_id="sess_1", turn_id="turn_1", session_event_publisher=pub
    )

    await runner.dispatch_observe(
        "pending_injection_consumed",
        {"session_id": "sess_1", "turn_id": "turn_1", "message_count": 1},
        ctx,
    )
    assert len(pub.events) == 0
