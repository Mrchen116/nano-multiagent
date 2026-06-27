"""Shared stubs for background_tasks integration tests.

Provides _FakeStore, _SessionManagerStub, _RuntimeStubBase, _RunsRegistryStub, and
_make_ctx so each test file only defines the parts that differ (primarily the run()
body and any extra __init__ fields).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.platform.tools.base import ToolContext


class _FakeStore:
    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self._sessions: dict[str, dict[str, Any]] = {}

    def resolve_path(
        self, session_id: str, *, workspace_root=None, parent_session_id: str = ""
    ) -> Path:
        path = self._tmp_path / "sessions" / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def find_session_by_metadata(
        self, *, parent_session_id: str, match: dict[str, Any], workspace_root=None
    ) -> str | None:
        for sid, meta in self._sessions.items():
            if all(meta.get(k) == v for k, v in match.items()):
                return sid
        return None


class _SessionManagerStub:
    def __init__(self, store: _FakeStore) -> None:
        self.store = store

    def load(
        self, session_id: str, *, workspace_root=None, parent_session_id: str = ""
    ) -> Any:
        meta = self.store._sessions.get(session_id, {})
        return type(
            "LoadResult",
            (),
            {
                "config": type("Config", (), {"metadata": meta})(),
            },
        )()


class _RuntimeStubBase:
    """Common runtime stub; subclasses must override ``run``."""

    def __init__(self, tmp_path: Path, delay: float = 0.0) -> None:
        self._tmp_path = tmp_path
        self._delay = delay
        self._counter = 0
        store = _FakeStore(tmp_path)
        self._session_manager = _SessionManagerStub(store)

    async def create_session(
        self,
        *,
        workspace_root: Any = None,
        skills: Any = None,
        metadata: Any = None,
        parent_session_id: str | None = None,
    ) -> Any:
        self._counter += 1
        sid = f"subagent_{self._counter}"
        self._session_manager.store._sessions[sid] = dict(metadata or {})
        return type("Session", (), {"session_id": sid})()

    def session_workspace_root(self, session_id: str) -> Any:
        return self._tmp_path

    def resolve_run_model(self, session_id: str | None) -> str | None:
        # bugfix-443: stub has no per-run model registry; the agent tool reads
        # this to thread the parent run model into subagent dispatch.
        return None

    def resolve_available_skills(
        self, workspace_root: Any, include_names: Any = None
    ) -> tuple:
        return ()


class _RunsRegistryStub:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.injections: list[dict[str, Any]] = []
        self._active_run_by_session: dict[str, str] = {}

    def get_active_run_id(self, session_id: str) -> str | None:
        return self._active_run_by_session.get(session_id)

    def get_event_loop(self) -> Any | None:
        return None

    @property
    def session_manager(self) -> None:
        # bugfix-404 F3: stub satisfies the public property added to RunsRegistry.
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
