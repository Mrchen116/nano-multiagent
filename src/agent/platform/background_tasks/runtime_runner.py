"""Typed SessionDirectory/KernelExecutor adapter for subagent work."""

from __future__ import annotations

import threading
import time
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any, Mapping

from agent.core.agent.run_control import RunController
from agent.core.background_tasks.interfaces import (
    BackgroundSubagentHandle,
    BackgroundSubagentRunner,
    ForegroundSubagentHandle,
    TaskCompletionCallback,
    TaskFailureCallback,
    TaskKillCallback,
)
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.executor import AuxiliaryHandle, KernelExecutor
from agent.core.runs.origin import RunOrigin
from agent.core.session.directory import SessionDirectory
from agent.core.session.types import SessionRef, TurnRequest


class RuntimeRunner(BackgroundSubagentRunner):
    """Resolve subagent conversations and submit only typed auxiliary targets."""

    def __init__(
        self,
        *,
        directory: SessionDirectory,
        executor: KernelExecutor,
    ) -> None:
        self._directory = directory
        self._executor = executor

    def start(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        on_complete: TaskCompletionCallback,
        on_fail: TaskFailureCallback,
        on_kill: TaskKillCallback,
        workspace_root: Path | None = None,
        llm_session_id: str | None = None,
        model: str | None = None,
    ) -> BackgroundSubagentHandle:
        """Start a callback-driven background auxiliary target."""

        root = _require_workspace_root(workspace_root)
        controller = RunController()
        auxiliary = self._start_auxiliary(
            agent_session_id=agent_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            workspace_root=root,
            llm_session_id=llm_session_id,
            model=model,
            controller=controller,
        )
        handle = _ControllerHandle(controller=controller, auxiliary=auxiliary)

        def _watch() -> None:
            started_at = time.monotonic()
            try:
                result = auxiliary.result()
            except CancelledError:
                on_kill(
                    task_id=agent_session_id,
                    result_text=None,
                    usage=None,
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                    tool_use_count=0,
                )
                return
            except Exception as exc:  # noqa: BLE001
                on_fail(task_id=agent_session_id, error=str(exc))
                return
            duration_ms = int((time.monotonic() - started_at) * 1000)
            callback = on_kill if controller.is_aborted else on_complete
            callback(
                task_id=agent_session_id,
                result_text=_extract_assistant_text(result),
                usage=_usage_to_dict(result.usage) if result.usage else None,
                duration_ms=duration_ms,
                tool_use_count=len(result.tool_calls) if result.tool_calls else 0,
            )

        threading.Thread(target=_watch, daemon=True).start()
        return handle

    def start_foreground(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        workspace_root: Path,
        llm_session_id: str | None = None,
        model: str | None = None,
    ) -> ForegroundSubagentHandle:
        """Start a result-bearing auxiliary target for foreground budgeting."""

        controller = RunController()
        auxiliary = self._start_auxiliary(
            agent_session_id=agent_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            workspace_root=workspace_root,
            llm_session_id=llm_session_id,
            model=model,
            controller=controller,
        )
        return _ControllerHandle(controller=controller, auxiliary=auxiliary)

    def _start_auxiliary(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        workspace_root: Path,
        llm_session_id: str | None,
        model: str | None,
        controller: RunController,
    ) -> AuxiliaryHandle:
        ref = SessionRef(
            session_id=agent_session_id,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id,
        )
        if self._directory.get(ref) is None:
            raise ValueError(f"subagent session does not exist: {agent_session_id}")
        session = self._directory.open(ref)
        return self._executor.start_auxiliary(
            agent_session_id,
            session,
            TurnRequest(
                parts=({"type": "text", "text": prompt},),
                llm_session_id=llm_session_id,
                controller=controller,
                origin=RunOrigin.BACKGROUND_TASK,
                model=model,
            ),
        )


class _ControllerHandle(ForegroundSubagentHandle):
    def __init__(
        self,
        *,
        controller: RunController,
        auxiliary: AuxiliaryHandle,
    ) -> None:
        self._controller = controller
        self._auxiliary = auxiliary

    def stop(self) -> None:
        self._controller.abort()
        self._auxiliary.cancel()

    def send_message(self, prompt: str) -> bool:
        return self._controller.enqueue_message(
            LLMMessage(role="user", content=prompt),
            origin=RunOrigin.USER,
        )

    def result(self, timeout: float | None = None):  # noqa: ANN201
        return self._auxiliary.result(timeout=timeout)


def _require_workspace_root(workspace_root: Path | None) -> Path:
    if workspace_root is None:
        raise ValueError("workspace_root is required for subagent execution")
    return workspace_root


def _extract_assistant_text(turn_result: Any) -> str | None:
    for message in reversed(getattr(turn_result, "messages", ())):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _usage_to_dict(usage: Any) -> Mapping[str, Any] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
    }
