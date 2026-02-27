from dataclasses import dataclass
from pathlib import Path

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
        return _Session(session_id=f"sess_task_blocking_{self.created}")

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
            turn_id="turn_blocking_integration",
            messages=(Message(message_id="msg_blocking", role="assistant", content="task-ok"),),
            completed=True,
            stop_reason="completed",
        )


def test_task_blocking_runs_through_tool_registry_with_runtime_wiring(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    result = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run integration",
            "prompt": "run integration task",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main_integration", repo_root=tmp_path),
    )

    assert result["mode"] == "blocking"
    assert result["run_in_background"] is False
    assert result["status"] == "completed"
    assert result["session_id"] == "sess_task_blocking_1"
    assert result["output"]["message"]["content"] == "task-ok"
    assert runtime.run_calls[0]["stream"] is False
