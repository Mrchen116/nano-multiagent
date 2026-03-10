from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.core.hooks.context import HookContext
from nano_multiagent.platform.http_api.app import create_app


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_load_skills_e2e_{self.created}")

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        del parts, stream, llm_session_id
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_load_skills_e2e",
            messages=(Message(message_id="msg_task_load_skills_e2e", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_task_load_skills_requires_existing_skill_name(tmp_path) -> None:  # noqa: ANN001
    app = create_app(auth_token="test-token", runtime=_RuntimeStub(), repo_root=tmp_path)
    client = TestClient(app)

    tools_resp = client.get("/v1/tools", headers=_auth_headers("req-task-load-skills-e2e"))
    assert tools_resp.status_code == 200

    with pytest.raises(ToolError, match="unknown skills requested"):
        app.state.tool_registry.execute(
            "task",
            {
                "run_in_background": False,
                "load_skills": ["missing-skill"],
                "description": "delegate task",
                "prompt": "run task",
                "category": "research",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        )
