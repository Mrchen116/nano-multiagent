"""Integration tests for submit/observe split endpoints (feat-338 M5)."""

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agent.core.agent.compaction.types import CompactionSettings
from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message, TurnResult
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.http_api.app import create_app


class _AsyncEchoLLM:
    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        yield LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}")
        yield LLMMessage(role="assistant", content="", finish_reason="completed")


class _AsyncBlockingRuntime:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.run_calls: list[tuple] = []
        self._compaction_settings = CompactionSettings()

    async def run(self, session_id, parts, *, stream=True, run_id=None, controller=None, **kwargs):
        self.run_calls.append((session_id, parts, run_id))
        # Poll a threading.Event so we work regardless of which event loop
        # the RunsRegistry worker thread uses.
        for _ in range(1000):
            if self.release.is_set():
                break
            await asyncio.sleep(0.01)
        if controller is not None and controller.is_aborted:
            return TurnResult(
                session_id=session_id,
                turn_id="turn_aborted",
                messages=(),
                completed=True,
                stop_reason="aborted",
            )
        return TurnResult(
            session_id=session_id,
            turn_id="turn_block",
            messages=(Message(message_id="msg_block", role="assistant", content="blocked"),),
            completed=True,
            stop_reason="completed",
        )

    async def fork_session(self, session_id: str):
        raise NotImplementedError

    async def compact(self, session_id: str):
        return None


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _parse_sse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event: dict[str, Any] = {}
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("id: "):
                event["id"] = line[4:]
            elif line.startswith("event: "):
                event["event"] = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])
        if data_lines:
            event["data"] = json.loads("".join(data_lines))
        events.append(event)
    return events


def _patch_hub_for_test(app) -> None:
    """Make persistent SSE stream close after a few empty ticks so tests can use response.text."""
    hub = app.state.event_stream_hub
    original = hub.stream_session

    async def _patched(self, *, session_id, after_sequence, tick_seconds=1.0, **kwargs):
        async for event in original(
            session_id=session_id,
            after_sequence=after_sequence,
            tick_seconds=tick_seconds,
            max_empty_ticks=2,
        ):
            yield event

    import types

    hub.stream_session = types.MethodType(_patched, hub)


def _wait_for_run_status(client: TestClient, run_id: str, status: str, *, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-poll-run"))
        if resp.status_code == 200 and resp.json()["status"] == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"run {run_id} did not reach status {status} in time")


def test_submit_message_returns_json_rpc(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_AsyncEchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-submit-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "hello"}]},
        headers=_auth_headers("req-submit-submit"),
    )
    assert submitted.status_code == 200
    payload = submitted.json()
    assert payload["run_id"].startswith("run_")
    assert isinstance(payload["anchor_sequence"], int)
    assert payload["injected"] is False
    assert payload["status"] == "queued"


def test_stream_replays_completed_run_events(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_AsyncEchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    app = create_app(session_store=store, runtime=runtime)
    _patch_hub_for_test(app)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-stream-replay-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "stream me"}]},
        headers=_auth_headers("req-stream-replay-submit"),
    )
    assert submitted.status_code == 200
    payload = submitted.json()
    run_id = payload["run_id"]
    anchor_sequence = payload["anchor_sequence"]

    _wait_for_run_status(client, run_id, "completed")

    response = client.get(
        f"/v1/sessions/{session_id}/stream",
        headers={**_auth_headers("req-stream-replay-stream"), "Last-Event-ID": str(anchor_sequence)},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    event_names = [e["event"] for e in events]
    assert "run_status" in event_names

    run_status_events = [e for e in events if e["event"] == "run_status" and e["data"].get("run_id") == run_id]
    statuses = [e["data"]["status"] for e in run_status_events]
    assert "queued" in statuses
    assert "completed" in statuses

    assistant_messages = [e for e in events if e["event"] == "assistant_message"]
    assert len(assistant_messages) >= 1
    assert assistant_messages[0]["data"]["content"] == "ack:stream me"


def test_stream_resume_with_last_event_id(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_AsyncEchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    app = create_app(session_store=store, runtime=runtime)
    _patch_hub_for_test(app)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-resume-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "resume test"}]},
        headers=_auth_headers("req-resume-submit"),
    )
    assert submitted.status_code == 200
    payload = submitted.json()
    run_id = payload["run_id"]
    anchor_sequence = payload["anchor_sequence"]

    _wait_for_run_status(client, run_id, "completed")

    # First pass: collect all events with their sequence ids.
    text = client.get(
        f"/v1/sessions/{session_id}/stream",
        headers={**_auth_headers("req-resume-first"), "Last-Event-ID": str(anchor_sequence)},
    ).text
    all_events = _parse_sse_events(text)
    assert len(all_events) >= 2

    # Pick a middle event id to resume from.
    resume_after_id = all_events[len(all_events) // 2]["id"]
    resume_after_seq = int(resume_after_id)

    # Second pass: resume from that sequence.
    resumed_text = client.get(
        f"/v1/sessions/{session_id}/stream",
        headers={**_auth_headers("req-resume-second"), "Last-Event-ID": str(resume_after_seq)},
    ).text
    resumed_events = _parse_sse_events(resumed_text)
    resumed_sequences = [int(e["id"]) for e in resumed_events]
    assert all(seq > resume_after_seq for seq in resumed_sequences)


def test_stream_resume_window_exceeded(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_AsyncEchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    app = create_app(session_store=store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-window-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    # Overflow the hub history so sequence 1 is pruned.
    # History then contains sequences 2..2001.  Last-Event-ID: 0 asks for events
    # after 0, but sequence 1 is missing → resume_window_exceeded.
    hub = app.state.event_stream_hub
    for i in range(2001):
        hub.publish(event="dummy", session_id="other_session", data={"index": i})

    text = client.get(
        f"/v1/sessions/{session_id}/stream",
        headers={**_auth_headers("req-window-stream"), "Last-Event-ID": "0"},
    ).text
    events = _parse_sse_events(text)
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert events[0]["data"]["code"] == "resume_window_exceeded"


def test_priority_now_preempts_active_run(tmp_path: Path) -> None:
    runtime = _AsyncBlockingRuntime()
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    app = create_app(session_store=store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-now-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}]},
        headers=_auth_headers("req-now-first"),
    )
    assert first.status_code == 200
    run_id_1 = first.json()["run_id"]

    _wait_for_run_status(client, run_id_1, "running")

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}], "priority": "now"},
        headers=_auth_headers("req-now-second"),
    )
    assert second.status_code == 200
    run_id_2 = second.json()["run_id"]

    runtime.release.set()

    _wait_for_run_status(client, run_id_2, "completed")

    run_1 = client.get(f"/v1/runs/{run_id_1}", headers=_auth_headers("req-now-get-1")).json()
    assert run_1["status"] == "cancelled"
    assert run_1["stop_reason"] == "aborted"

    run_2 = client.get(f"/v1/runs/{run_id_2}", headers=_auth_headers("req-now-get-2")).json()
    assert run_2["status"] == "completed"


def test_priority_next_injects_into_active_run(tmp_path: Path) -> None:
    runtime = _AsyncBlockingRuntime()
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    app = create_app(session_store=store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-next-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}]},
        headers=_auth_headers("req-next-first"),
    )
    assert first.status_code == 200
    run_id_1 = first.json()["run_id"]

    _wait_for_run_status(client, run_id_1, "running")

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}], "priority": "next"},
        headers=_auth_headers("req-next-second"),
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["injected"] is True
    assert payload["status"] == "injected"
    assert payload["run_id"] == run_id_1

    runtime.release.set()
    _wait_for_run_status(client, run_id_1, "completed")
