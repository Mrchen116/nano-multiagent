from dataclasses import dataclass
from pathlib import Path
from time import sleep

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.task import TaskTool


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_nb_{self.created}")

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
        sleep(0.05)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_nb",
            messages=(Message(message_id="msg_nb", role="assistant", content="nb-ok"),),
            completed=True,
            stop_reason="completed",
        )

    def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        return self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
        )


def _context(tmp_path: Path) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session("sess_main_unit")


def test_task_non_blocking_returns_receipt_and_reuses_idempotency_key(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)
    ctx = _context(tmp_path)

    first = tool.run(
        {
            "mode": "non_blocking",
            "prompt": "run",
            "subagent_type": "oracle",
            "idempotency_key": "idem-1",
        },
        ctx,
    )
    second = tool.run(
        {
            "mode": "non_blocking",
            "prompt": "run",
            "subagent_type": "oracle",
            "idempotency_key": "idem-1",
        },
        ctx,
    )

    assert first["status"] == "running"
    assert first["mode"] == "non_blocking"
    assert first["task_id"]
    assert first["session_id"].startswith("sess_task_nb_")
    assert second["task_id"] == first["task_id"]
    assert second["idempotency_reused"] is True


def test_task_continuation_rejects_category_or_subagent_type_mix(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    with pytest.raises(ToolError, match="session_id cannot be combined"):
        tool.run(
            {
                "mode": "blocking",
                "session_id": "sess_existing",
                "prompt": "continue",
                "category": "analysis",
            },
            _context(tmp_path),
        )


def test_task_new_task_requires_exactly_one_category_or_subagent_type(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="exactly one of 'category' or 'subagent_type'"):
        tool.run({"mode": "blocking", "prompt": "missing selector"}, ctx)

    with pytest.raises(ToolError, match="exactly one of 'category' or 'subagent_type'"):
        tool.run(
            {
                "mode": "blocking",
                "prompt": "conflict selector",
                "category": "analysis",
                "subagent_type": "oracle",
            },
            ctx,
        )
