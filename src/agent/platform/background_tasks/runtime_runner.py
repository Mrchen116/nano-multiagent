"""Adapter connecting AgentRuntime to BackgroundSubagentRunner."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Mapping

from agent.core.agent.run_control import RunController
from agent.core.agent.runtime import AgentRuntime
from agent.core.background_tasks.interfaces import (
    BackgroundSubagentRunner,
    BackgroundTaskStopper,
    TaskCompletionCallback,
    TaskFailureCallback,
)


class RuntimeRunner(BackgroundSubagentRunner):
    """Run subagent turns via AgentRuntime in a dedicated event loop.

    When an *event_loop* is provided (e.g. ``RunsRegistry``'s dedicated loop),
    subagent work is submitted to that loop so that shared ``AgentRuntime``
    async primitives (``asyncio.Lock``, ``asyncio.Event``) are bound to the
    correct loop.  Without an explicit loop the runner falls back to spawning
    a new daemon thread + ``asyncio.run()``.
    """

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._runtime = runtime
        self._event_loop = event_loop

    def start(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        on_complete: TaskCompletionCallback,
        on_fail: TaskFailureCallback,
    ) -> BackgroundTaskStopper:
        controller = RunController()

        async def _worker() -> None:
            start = time.monotonic()
            try:
                turn_result = await self._runtime.run(
                    agent_session_id,
                    [{"type": "text", "text": prompt}],
                    stream=False,
                    controller=controller,
                    parent_session_id=parent_session_id,
                )
            except Exception as exc:
                on_fail(task_id=agent_session_id, error=str(exc))
                return

            duration_ms = int((time.monotonic() - start) * 1000)
            result_text = _extract_assistant_text(turn_result)
            usage = _usage_to_dict(turn_result.usage) if turn_result.usage else None
            tool_use_count = len(turn_result.tool_calls) if turn_result.tool_calls else 0

            try:
                on_complete(
                    task_id=agent_session_id,
                    result_text=result_text,
                    usage=usage,
                    duration_ms=duration_ms,
                    tool_use_count=tool_use_count,
                )
            except Exception:
                pass

        if self._event_loop is not None:
            asyncio.run_coroutine_threadsafe(_worker(), self._event_loop)
        else:

            def _thread_worker() -> None:
                asyncio.run(_worker())

            threading.Thread(target=_thread_worker, daemon=True).start()

        return _ControllerStopper(controller)


class _ControllerStopper:
    def __init__(self, controller: RunController) -> None:
        self._controller = controller

    def stop(self) -> None:
        self._controller.abort()


def _extract_assistant_text(turn_result: Any) -> str | None:
    messages = getattr(turn_result, "messages", ())
    for message in reversed(messages):
        if getattr(message, "role", None) == "assistant":
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
