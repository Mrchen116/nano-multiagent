"""bugfix-417-M3 R2: realtime_stream 把工具执行心跳投影为 run_heartbeat 进 stream.

R1 让 tools/registry 在工具运行期实时 dispatch `tool_execution_update`。R2 在
realtime_stream 加一个 observe handler 把携带 `phase:running` 的更新 publish 成
`run_heartbeat` session event —— 这是三类 liveness 源(工具/LLM/权限)进 kernel.stream 的
同一事件类型。纯 liveness,前端可忽略其内容;承载结果的最终 update(无 phase,带 output)
不应被当心跳 publish,避免事件噪音。
"""

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.platform.hooks.builtins.realtime_stream import setup as setup_realtime_stream


class _FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def __call__(self, event: str, data: dict[str, object]) -> None:
        self.events.append({"event": event, "data": data})


def _make_ctx(publisher: _FakePublisher) -> HookContext:
    return HookContext(
        session_id="sess_1",
        turn_id="turn_1",
        metadata={"run_id": "run_1"},
        session_event_publisher=publisher,
    )


async def test_tool_execution_update_running_emits_run_heartbeat() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(pub)

    diagnostics = await runner.dispatch_observe(
        "tool_execution_update",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "name": "bash",
            "tool_call_id": "call_1",
            "run_id": "run_1",
            "phase": "running",
            "status": "running",
            "elapsed_ms": 4200,
        },
        ctx,
    )
    assert all(d.status == "ok" for d in diagnostics)
    assert len(pub.events) == 1
    evt = pub.events[0]
    assert evt["event"] == "run_heartbeat"
    assert evt["data"]["event"] == "run_heartbeat"
    assert evt["data"]["run_id"] == "run_1"
    assert evt["data"]["phase"] == "running"
    assert evt["data"]["elapsed_ms"] == 4200


async def test_tool_execution_update_final_output_not_a_heartbeat() -> None:
    """The authoritative final update (carries output, no phase) must NOT publish a
    run_heartbeat — only liveness ticks do, to keep the stream free of duplicate noise.
    """
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(pub)

    await runner.dispatch_observe(
        "tool_execution_update",
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "name": "bash",
            "tool_call_id": "call_1",
            "run_id": "run_1",
            "output": {"stdout": "done"},
        },
        ctx,
    )
    assert pub.events == []


async def test_tool_execution_update_without_run_id_skipped() -> None:
    hooks = HookRegistry()
    setup_realtime_stream(hooks)
    runner = HookRunner(registry=hooks)
    pub = _FakePublisher()
    ctx = _make_ctx(pub)

    await runner.dispatch_observe(
        "tool_execution_update",
        {"session_id": "sess_1", "phase": "running", "elapsed_ms": 1},
        ctx,
    )
    assert pub.events == []
