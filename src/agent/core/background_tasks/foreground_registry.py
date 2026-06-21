"""Foreground execution registry: in-flight foreground-tool stop handles by session.

bugfix-417-M7 (decision 12): foreground bash no longer registers into
``BackgroundTaskRegistry``. A synchronous foreground command returns its result via
the tool result; the ONLY background-task facility it genuinely needs is a handle to
killpg its subprocess tree on /stop or cancel (the subprocess lives in a ``to_thread``
worker that async cancel cannot reach — see decision 10). This registry holds exactly
that, and nothing else — no record persistence, no terminal state machine, no
``<task-notification>`` delivery. With the foreground command physically absent from
``BackgroundTaskRegistry``, the dual-channel bug (tool result + notification) cannot
recur structurally rather than being suppressed by a ``notified`` flag.

Core layer, platform-free: the stopper is an injected port (``BackgroundTaskStopper``
Protocol), so this stays importable from ``agent.core`` without touching the platform
runner.
"""

from __future__ import annotations

import threading

from agent.core.background_tasks.interfaces import BackgroundTaskStopper


class ForegroundExecutionRegistry:
    """Tracks in-flight foreground-tool stop handles keyed by parent session.

    ``stop_for_session`` is wired by the kernel into the core ``RunsRegistry`` as the
    ``ForegroundStopper`` port (same ``(session_id) -> bool`` signature the M5
    ``BackgroundTaskRegistry.stop_foreground_for_session`` had), so interrupt/cancel
    reaps the run-blocking foreground subprocess while leaving user-launched
    background tasks (which live in ``BackgroundTaskRegistry``) untouched.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stoppers: dict[str, list[BackgroundTaskStopper]] = {}

    def register(self, *, session_id: str, stopper: BackgroundTaskStopper) -> None:
        with self._lock:
            self._stoppers.setdefault(session_id, []).append(stopper)

    def unregister(
        self, *, session_id: str, stopper: BackgroundTaskStopper | None = None
    ) -> None:
        """Drop a session's foreground stopper.

        With ``stopper`` given, removes that one handle (used by auto-background
        hand-off and on completion); without it, clears all handles for the session.
        Unknown sessions are a safe no-op — completion and hand-off can race a /stop
        that already cleared the entry.
        """
        with self._lock:
            handles = self._stoppers.get(session_id)
            if handles is None:
                return
            if stopper is None:
                del self._stoppers[session_id]
                return
            try:
                handles.remove(stopper)
            except ValueError:
                pass
            if not handles:
                del self._stoppers[session_id]

    def stop_for_session(self, session_id: str) -> bool:
        """Stop every in-flight foreground tool of a session (killpg via its handle).

        Returns:
            True if at least one foreground stopper was found and fired, False
            otherwise. The caller (RunsRegistry interrupt/cancel) uses this to decide
            whether it must additionally force-cancel the parked carrier Task.
        """
        with self._lock:
            handles = list(self._stoppers.get(session_id, ()))
        for handle in handles:
            handle.stop()
        return bool(handles)
