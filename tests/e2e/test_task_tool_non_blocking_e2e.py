import time
from dataclasses import dataclass

from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.server.app import create_app


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_non_blocking_e2e_{self.created}")

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        self.run_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "stream": stream,
                "llm_session_id": llm_session_id,
            }
        )
        return TurnResult(
            session_id=session_id,
            turn_id="turn_non_blocking_e2e",
            messages=(Message(message_id="msg_non_blocking_e2e", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )

    def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None, run_id: str | None = None) -> TurnResult:
        return self.run(session_id, [{"type": "text", "text": "continue"}], stream=stream, llm_session_id=llm_session_id)


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for(predicate, *, timeout_seconds: float = 0.5) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_non_blocking_task_receipt_is_returned_without_new_http_endpoint(tmp_path) -> None:  # noqa: ANN001
    runtime = _RuntimeStub()
    app = create_app(auth_token="test-token", runtime=runtime, repo_root=tmp_path)
    client = TestClient(app)

    tools_resp = client.get("/v1/tools", headers=_auth_headers("req-task-non-blocking-e2e"))
    assert tools_resp.status_code == 200
    assert "/v1/tasks" not in {route.path for route in app.routes}

    receipt = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": True,
            "load_skills": [],
            "description": "delegate task",
            "prompt": "delegate",
            "category": "research",
        },
        hook_context=HookContext(session_id="sess_main_non_blocking_e2e", repo_root=tmp_path),
    )

    assert receipt["mode"] == "non_blocking"
    assert receipt["run_in_background"] is True
    assert receipt["status"] == "queued"
    assert receipt["task_id"].startswith("call_")
    assert receipt["session_id"] == "sess_non_blocking_e2e_1"
    _wait_for(lambda: len(runtime.run_calls) == 1)
