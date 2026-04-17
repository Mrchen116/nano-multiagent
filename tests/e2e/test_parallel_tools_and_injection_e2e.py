"""E2E tests for parallel tool execution and round-boundary message injection."""

import asyncio
import time
from threading import Event

from fastapi.testclient import TestClient

from agent.core.agent.run_control import RunController
from agent.core.agent.tool_executor import ToolBatch, ToolExecutor, partition_into_batches
from agent.core.runs.registry import RunsRegistry
from agent.core.types import Message, ToolCall, ToolResult, TurnResult
from agent.platform.http_api.app import create_app


# ---------------------------------------------------------------------------
# partition_into_batches unit tests
# ---------------------------------------------------------------------------

def test_partition_empty_calls():
    assert partition_into_batches([], {}) == []


def test_partition_all_unsafe():
    calls = [
        ToolCall(call_id="c1", name="bash", arguments={}),
        ToolCall(call_id="c2", name="write", arguments={}),
    ]
    batches = partition_into_batches(calls, {"bash": False, "write": False})
    assert len(batches) == 2
    assert all(not b.concurrent for b in batches)
    assert batches[0].calls == (calls[0],)
    assert batches[1].calls == (calls[1],)


def test_partition_all_safe():
    calls = [
        ToolCall(call_id="c1", name="read", arguments={}),
        ToolCall(call_id="c2", name="read", arguments={}),
        ToolCall(call_id="c3", name="read", arguments={}),
    ]
    batches = partition_into_batches(calls, {"read": True})
    assert len(batches) == 1
    assert batches[0].concurrent is True
    assert len(batches[0].calls) == 3


def test_partition_mixed_safe_unsafe_safe():
    calls = [
        ToolCall(call_id="c1", name="read", arguments={}),
        ToolCall(call_id="c2", name="read", arguments={}),
        ToolCall(call_id="c3", name="bash", arguments={}),
        ToolCall(call_id="c4", name="read", arguments={}),
    ]
    batches = partition_into_batches(calls, {"read": True, "bash": False})
    assert len(batches) == 3
    assert batches[0].concurrent is True
    assert len(batches[0].calls) == 2
    assert batches[1].concurrent is False
    assert batches[1].calls[0].call_id == "c3"
    assert batches[2].concurrent is True
    assert batches[2].calls[0].call_id == "c4"


def test_partition_unknown_tool_treated_as_unsafe():
    calls = [ToolCall(call_id="c1", name="unknown_tool", arguments={})]
    batches = partition_into_batches(calls, {})
    assert len(batches) == 1
    assert batches[0].concurrent is False


# ---------------------------------------------------------------------------
# ToolExecutor unit tests
# ---------------------------------------------------------------------------

async def _make_result(call: ToolCall) -> ToolResult:
    return ToolResult(call_id=call.call_id, name=call.name, output=f"ok:{call.call_id}")


async def _make_error(call: ToolCall) -> ToolResult:
    raise ValueError(f"tool error for {call.call_id}")


def test_tool_executor_serial_batch():
    batch = ToolBatch(
        calls=(ToolCall(call_id="c1", name="bash", arguments={}),),
        concurrent=False,
    )
    executor = ToolExecutor()
    results = asyncio.run(executor.execute(batch, _make_result))
    assert len(results) == 1
    assert results[0].output == "ok:c1"


def test_tool_executor_concurrent_batch_returns_all():
    calls = tuple(
        ToolCall(call_id=f"c{i}", name="read", arguments={}) for i in range(3)
    )
    batch = ToolBatch(calls=calls, concurrent=True)
    executor = ToolExecutor()
    results = asyncio.run(executor.execute(batch, _make_result))
    assert len(results) == 3
    assert {r.output for r in results} == {"ok:c0", "ok:c1", "ok:c2"}


def test_tool_executor_concurrent_error_becomes_tool_error():
    calls = (
        ToolCall(call_id="c1", name="read", arguments={}),
        ToolCall(call_id="c2", name="read", arguments={}),
    )
    batch = ToolBatch(calls=calls, concurrent=True)
    executor = ToolExecutor()

    async def mixed(call: ToolCall) -> ToolResult:
        if call.call_id == "c1":
            return await _make_result(call)
        raise ValueError("simulated failure")

    results = asyncio.run(executor.execute(batch, mixed))
    assert len(results) == 2
    ok = next(r for r in results if r.call_id == "c1")
    err = next(r for r in results if r.call_id == "c2")
    assert ok.output == "ok:c1"
    assert err.error is not None
    assert "simulated failure" in err.error


# ---------------------------------------------------------------------------
# RunController unit tests
# ---------------------------------------------------------------------------

def test_run_controller_cancel():
    ctrl = RunController()
    assert not ctrl.is_cancelled
    ctrl.cancel()
    assert ctrl.is_cancelled


def test_run_controller_abort():
    ctrl = RunController()
    assert not ctrl.is_aborted
    ctrl.abort()
    assert ctrl.is_aborted


def test_run_controller_enqueue_and_drain():
    from agent.core.llm.interfaces import LLMMessage

    ctrl = RunController()
    assert ctrl.drain_pending() == []

    msg1 = LLMMessage(role="user", content="hello")
    msg2 = LLMMessage(role="user", content="world")
    ctrl.enqueue_message(msg1)
    ctrl.enqueue_message(msg2)

    drained = ctrl.drain_pending()
    assert len(drained) == 2
    assert drained[0].content == "hello"
    assert drained[1].content == "world"
    assert ctrl.drain_pending() == []  # queue is empty after drain


# ---------------------------------------------------------------------------
# HTTP API: priority='next' injection e2e test
# ---------------------------------------------------------------------------

def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_running(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-poll"))
        if resp.status_code == 200 and resp.json()["status"] == "running":
            return
        time.sleep(0.02)
    raise AssertionError("run never reached running status")


def _wait_for_terminal(client: TestClient, run_id: str, *, timeout_seconds: float = 3.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-poll"))
        if resp.status_code == 200 and resp.json()["status"] in {"completed", "failed", "cancelled"}:
            return resp.json()
        time.sleep(0.02)
    raise AssertionError("run never reached terminal status")


class _BlockingRuntime:
    """Async runtime stub that blocks until released, capturing controller."""

    def __init__(self) -> None:
        self.release = Event()
        self.received_controller: RunController | None = None
        self.call_count = 0

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller: RunController | None = None,
    ) -> TurnResult:
        self.call_count += 1
        self.received_controller = controller
        self.release.wait(timeout=5.0)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_inject_e2e",
            messages=(Message(message_id="msg_inject", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )


def test_priority_next_injects_into_active_run_e2e() -> None:
    """priority='next' returns 202 and enqueues message into the active run's controller."""
    runtime = _BlockingRuntime()
    client = TestClient(create_app(runtime=runtime), raise_server_exceptions=False)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-inject-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    # Start an async run (it will block until released)
    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "start"}]},
        headers=_auth_headers("req-inject-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    # Inject with priority='next' while run is active
    injected = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "injected message"}], "priority": "next"},
        headers=_auth_headers("req-inject-msg"),
    )
    assert injected.status_code == 202
    # Status should be 'injected' not a new run_id
    assert injected.json().get("status") == "injected"
    assert injected.json().get("run_id") == run_id

    # Release the runtime
    runtime.release.set()
    _wait_for_terminal(client, run_id)

    assert runtime.call_count == 1


def test_priority_now_interrupts_active_run_e2e() -> None:
    """priority='now' signals abort on the active run's controller."""
    runtime = _BlockingRuntime()
    client = TestClient(create_app(runtime=runtime), raise_server_exceptions=False)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-now-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "start"}]},
        headers=_auth_headers("req-now-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    # Confirm controller was passed to runtime
    assert runtime.received_controller is not None
    controller = runtime.received_controller

    # Interrupt via priority='now' (async endpoint)
    client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "interrupt"}], "priority": "now"},
        headers=_auth_headers("req-now-interrupt"),
    )

    # The controller should be aborted
    assert controller.is_aborted

    runtime.release.set()
