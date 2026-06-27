"""Adapter connecting AgentRuntime to BackgroundSubagentRunner."""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Coroutine, Mapping

from agent.core.agent.run_control import RunController
from agent.core.agent.runtime import AgentRuntime
from agent.core.background_tasks.interfaces import (
    BackgroundSubagentRunner,
    BackgroundTaskStopper,
    TaskCompletionCallback,
    TaskFailureCallback,
    TaskKillCallback,
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
        on_kill: TaskKillCallback,
        workspace_root: Path | None = None,
        llm_session_id: str | None = None,
        model: str | None = None,
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
                    workspace_root=workspace_root,
                    llm_session_id=llm_session_id,
                    model=model,
                )
            except Exception as exc:
                on_fail(task_id=agent_session_id, error=str(exc))
                return

            duration_ms = int((time.monotonic() - start) * 1000)
            result_text = _extract_assistant_text(turn_result)
            usage = _usage_to_dict(turn_result.usage) if turn_result.usage else None
            tool_use_count = (
                len(turn_result.tool_calls) if turn_result.tool_calls else 0
            )

            try:
                # bugfix-420 decisions 2 & 3: a cooperative abort (task_stop on a
                # subagent) lets runtime.run *return* a TurnResult carrying the
                # messages accumulated up to the abort. Route to on_kill so the
                # killed <task-notification> carries the partial result, instead
                # of on_complete (which would mislabel the terminal as completed).
                if controller.is_aborted:
                    on_kill(
                        task_id=agent_session_id,
                        result_text=result_text,
                        usage=usage,
                        duration_ms=duration_ms,
                        tool_use_count=tool_use_count,
                    )
                else:
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

    def submit_foreground(self, coro: Coroutine[Any, Any, Any]) -> Future:
        """Submit a foreground subagent coroutine onto the dedicated loop.

        bugfix-418: the foreground ``agent`` tool path used to run a *shared*
        AgentRuntime via bare ``asyncio.run`` in a private ThreadPoolExecutor,
        which spun up a transient loop. Awaiting an AgentRuntime primitive bound
        to the dedicated loop (per-session ``asyncio.Lock``, shared httpx client)
        then raised ``... is bound to a different event loop`` and the transient
        loop polluted the shared singleton, silently killing the consumer's
        resident heartbeat/relay coroutines.

        Submitting onto ``RunsRegistry``'s dedicated loop (the same loop that
        created those primitives) eliminates the cross-loop fault, and running as
        an independent Task on that loop isolates the subagent's failure to the
        returned ``Future`` — it cannot kill the loop or sibling runs.

        The caller blocks on the returned ``concurrent.futures.Future`` with a
        timeout to implement the foreground budget; this blocks the tool *thread*
        (spawned by ``asyncio.to_thread``), not the dedicated loop, which keeps
        servicing this and other Tasks. Unlike :meth:`start`, this submits the
        *bare* coroutine (returns its value, no completion callback), so an
        in-budget result is never re-delivered as a ``<task-notification>``.

        When no dedicated loop is wired (defensive: pure-library assembly without
        a RunsRegistry), the coroutine runs on its own isolated loop in a daemon
        thread — never sharing the caller's loop.
        """
        if self._event_loop is not None:
            return asyncio.run_coroutine_threadsafe(coro, self._event_loop)

        future: Future = Future()

        def _thread_worker() -> None:
            try:
                future.set_result(asyncio.run(coro))
            except BaseException as exc:  # noqa: BLE001
                future.set_exception(exc)

        threading.Thread(target=_thread_worker, daemon=True).start()
        return future


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
