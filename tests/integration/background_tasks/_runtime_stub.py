"""Shared final-interface stubs for background-task integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.platform.tools.base import ToolContext


class _RunsRegistryStub:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.injections: list[dict[str, Any]] = []
        self._active_run_by_session: dict[str, str] = {}

    def get_active_run_id(self, session_id: str) -> str | None:
        return self._active_run_by_session.get(session_id)

    def get_event_loop(self) -> Any | None:
        return None

    def inject_pending_message(
        self,
        session_id: str,
        message: LLMMessage,
        origin: RunOrigin = RunOrigin.USER,
    ) -> bool:
        # bugfix-426: inject_pending_message gained an origin param.
        self.injections.append(
            {"session_id": session_id, "message": message, "origin": origin}
        )
        return True

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        trace_id: str | None = None,
        workspace_root: Any = None,
    ) -> Any:
        self.submissions.append(
            {
                "session_id": session_id,
                "parts": parts,
                "origin": origin,
                "source_task_id": source_task_id,
                "workspace_root": workspace_root,
            }
        )
        return type(
            "RunRecord",
            (),
            {"run_id": "run_1", "session_id": session_id, "status": "queued"},
        )()


def _make_ctx(tmp_path: Path, session_id: str = "sess_parent") -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session(session_id=session_id)
