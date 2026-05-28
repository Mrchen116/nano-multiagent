import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.types import Message, TurnResult
from agent.core.hooks.context import HookContext
from agent.platform.hooks.loader import build_hook_registry
from agent.core.hooks.runner import HookRunner
from agent.platform.hooks.session_events import get_session_event_publisher
from agent.platform.http_api.app import create_app


class _RuntimeStub:
    def __init__(self) -> None:
        self.hook_registry = build_hook_registry(repo_root=Path.cwd())
        self.hook_runner = HookRunner(registry=self.hook_registry)

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None, workspace_root=None):  # noqa: ANN001, ANN201
        del parts
        del stream
        turn_id = "turn_sse_contract"
        hook_ctx = HookContext(
            session_id=session_id,
            turn_id=turn_id,
            metadata={"run_id": run_id} if run_id is not None else {},
            session_event_publisher=get_session_event_publisher(
                registry=self.hook_registry,
                session_id=session_id,
            ),
        )
        # tool_call → realtime_stream publishes "tool_start" SSE event
        await self.hook_runner.dispatch_observe(
            "tool_call",
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "run_id": run_id,
                "call_id": "call_sse_contract",
                "name": "bash",
                "arguments": {"command": "echo hi"},
            },
            hook_ctx,
        )
        # tool_result → realtime_stream publishes "tool_end" SSE event
        await self.hook_runner.dispatch_observe(
            "tool_result",
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "run_id": run_id,
                "call_id": "call_sse_contract",
                "name": "bash",
                "output": "hi",
                "error": None,
                "duration_ms": 220,
            },
            hook_ctx,
        )
        # message_end → realtime_stream publishes "assistant_message" SSE event
        await self.hook_runner.dispatch_observe(
            "message_end",
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "run_id": run_id,
                "message_id": "msg_sse_contract",
                "content": "contract-sse",
                "role": "assistant",
            },
            hook_ctx,
        )
        # turn_end → realtime_stream publishes "turn_end" SSE event
        await self.hook_runner.dispatch_observe(
            "turn_end",
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "completed": True,
                "stop_reason": "completed",
                "run_id": run_id,
            },
            hook_ctx,
        )
        return TurnResult(
            session_id=session_id,
            turn_id=turn_id,
            messages=(Message(message_id="msg_sse_contract", role="assistant", content="contract-sse"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_global_sse_contract_returns_event_stream_frames(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runtime=_RuntimeStub(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-contract-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-sse-contract-submit"),
    )
    assert submitted.status_code == 200

    response = client.get("/v1/events?after_sequence=0&max_events=16&timeout_seconds=0.1", headers=_auth_headers("req-sse-contract-global"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: run_status" in body
    assert "event: tool_start" in body
    assert "event: tool_end" in body
    assert "event: assistant_message" in body
    assert "event: turn_end" in body


def test_session_sse_contract_filters_by_session_id(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runtime=_RuntimeStub(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-contract-create-2"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "session-only"}]},
        headers=_auth_headers("req-sse-contract-submit-2"),
    )
    assert submitted.status_code == 200

    response = client.get(
        f"/v1/events?after_sequence=0&max_events=8&timeout_seconds=0.1",
        headers=_auth_headers("req-sse-contract-session"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_status" in response.text
    assert session_id in response.text
