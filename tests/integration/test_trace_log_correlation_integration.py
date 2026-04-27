import time
from pathlib import Path

from agent.core.types import Message, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.observability.logger import capture_logs
from agent.core.observability.tracing import bind_correlation
from agent.core.runs.registry import RunsRegistry
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry


class _RuntimeStub:
    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None):  # noqa: ANN001, ANN201
        del parts, stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_obs_integration",
            messages=(Message(message_id="msg_obs", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _EchoTool:
    name = "echo"
    description = "Echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        del ctx
        return {"text": args["text"]}


def test_run_tool_hook_logs_share_correlation_fields(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "obs-integration.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)

    runs = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    hooks = HookRegistry()

    async def break_on_tool_start(payload, ctx):
        del payload, ctx
        raise RuntimeError("boom")

    hooks.on("tool_execution_start", break_on_tool_start, source="runtime")
    tools = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    tools.register(_EchoTool())

    with capture_logs() as records:
        with bind_correlation(session_id=session.session_id, turn_id="turn_obs_integration", trace_id="trace_obs_integration"):
            run_record = runs.submit(
                session_id=session.session_id,
                parts=[{"type": "text", "text": "ping"}],
                trace_id="trace_obs_integration",
            )
            deadline = time.time() + 1.0
            while time.time() < deadline:
                current = runs.get(run_record.run_id)
                if current is not None and current.status.value in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.01)

            tools.execute(
                "echo",
                {"text": "hi"},
                hook_context=HookContext(
                    session_id=session.session_id,
                    turn_id="turn_obs_integration",
                    repo_root=Path.cwd(),
                    metadata={"tool_call_id": "call_obs_integration"},
                ),
            )

    by_message = {item["message"] for item in records}
    assert "run_submitted" in by_message
    assert "tool_execution_start" in by_message
    hook_logs = [item for item in records if item["message"] == "hook execution isolated"]
    assert hook_logs

    hook_fields = hook_logs[0]["fields"]
    assert hook_fields["session_id"] == session.session_id
    assert hook_fields["turn_id"] == "turn_obs_integration"
    assert hook_fields["tool_call_id"] == "call_obs_integration"
    assert hook_fields["trace_id"] == "trace_obs_integration"

    runs.shutdown()
