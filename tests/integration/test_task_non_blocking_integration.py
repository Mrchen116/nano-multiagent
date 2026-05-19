import time
from dataclasses import dataclass
from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.core.types import Message, TurnResult
from agent.platform.persistence.session.service import SessionService


class _RecordingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="subagent-ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    async def create_session(self, *, title: str | None = None, metadata=None) -> _Session:
        del title, metadata
        self.created += 1
        return _Session(session_id=f"sess_non_blocking_integration_{self.created}")

    async def run(
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
        time.sleep(0.05)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_non_blocking_integration",
            messages=(Message(message_id="msg_non_blocking_integration", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None):  # noqa: ANN201
        del stream, llm_session_id
        return await self.run(session_id, [{"type": "text", "text": "continue"}], stream=False)


def _wait_for(predicate, *, timeout_seconds: float = 0.6) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


async def test_task_blocking_passes_parent_session_id_to_subagent_llm(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    llm_client = _RecordingLLMClient()
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm_client,
        model="mock-model",
    )
    app = create_app(runtime=runtime, session_store=service.manager.store, repo_root=tmp_path)

    result = await app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "delegate task",
            "prompt": "delegate this",
            "category": "research",
        },
        hook_context=HookContext(session_id="sess_main_header", repo_root=tmp_path),
    )

    assert result["result"].startswith("Task completed in ")
    assert "<task_metadata>\nsession_id:" in result["result"]
    assert "sess_main_header" not in result["result"]
    assert llm_client.requests[0].session_id == "sess_main_header"


def test_task_non_blocking_executes_on_same_node_and_returns_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        app.state.tool_registry.execute(
            "task",
            {
                "run_in_background": True,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "run async",
                "subagent_type": "oracle",
            },
            hook_context=HookContext(session_id="sess_main_non_blocking", repo_root=tmp_path),
        )
    )

    assert result["result"].startswith("Background task launched.")
    assert "Status: queued" in result["result"]
    assert "<task_metadata>\nsession_id: sess_non_blocking_integration_1\n</task_metadata>" in result["result"]
    _wait_for(lambda: len(runtime.run_calls) == 1)
