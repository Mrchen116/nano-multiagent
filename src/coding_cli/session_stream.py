"""Background SSE stream reader for REPL session."""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Callable

from coding_cli.client import ServerClient


_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class SessionStreamReader:
    """Background thread that owns a persistent stream_session() iterator.

    Events are pushed into a thread-safe queue. Consumers poll for events
    belonging to a specific run_id.
    """

    def __init__(self, client: ServerClient) -> None:
        self._client = client
        self._event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=4096)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._session_id: str | None = None
        self._last_event_id: int | None = None
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str | None:
        """Return the currently configured session id."""
        return self._session_id

    def start(self, *, session_id: str) -> None:
        """Start the background reader thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._session_id = session_id
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        """Main loop: maintain persistent SSE connection and enqueue events."""
        while not self._stop_event.is_set():
            try:
                asyncio.run(self._stream_loop())
            except Exception:
                # On disconnect or error, wait a bit and reconnect.
                # TODO(feat-338): log reconnection attempt.
                pass
            if self._stop_event.wait(1.0):
                break

    async def _stream_loop(self) -> None:
        session_id = self._session_id
        if session_id is None:
            return
        last_event_id: int | None = None
        with self._lock:
            last_event_id = self._last_event_id
        async for event in self._client.stream_session(
            session_id=session_id,
            last_event_id=last_event_id,
        ):
            if self._stop_event.is_set():
                break
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                # Drop oldest events on overflow.
                try:
                    self._event_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._event_queue.put_nowait(event)
                except queue.Full:
                    pass
            event_id = event.get("_id")
            if isinstance(event_id, int):
                with self._lock:
                    self._last_event_id = event_id

    def poll(self, timeout: float = 0.1) -> dict[str, Any] | None:
        """Poll one event from the queue. Return None on timeout."""
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_run(
        self,
        run_id: str,
        *,
        timeout: float = 0.5,
        idle_timeout: float = 1800.0,
        on_other: Callable[[dict[str, Any]], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Block until terminal run_status for run_id, collecting all matching events.

        Non-matching events are passed to ``on_other`` if provided, otherwise
        discarded.  Matching events are passed to ``on_event`` immediately as
        they arrive (before being appended to the returned list), enabling
        real-time rendering during the drain loop.

        The idle_timeout is reset each time an event belonging to this run_id
        arrives.  Only continuous silence (no matching events for idle_timeout
        seconds) triggers TimeoutError — there is no absolute wall-clock cap.
        This correctly handles long-running coding agent tasks that may take
        many minutes while still detecting truly stalled runs.

        Raises TimeoutError if no run_id-matching event arrives within idle_timeout.
        """
        import time

        events: list[dict[str, Any]] = []
        # Deadline is extended every time we receive a matching event.
        # Only reset by events belonging to this run — other-run events
        # do not indicate this run is still active.
        deadline = time.monotonic() + idle_timeout
        while time.monotonic() < deadline:
            evt = self.poll(timeout=timeout)
            if evt is None:
                continue
            if evt.get("run_id") != run_id:
                if on_other is not None:
                    on_other(evt)
                continue
            # This run is alive: push the idle deadline forward.
            deadline = time.monotonic() + idle_timeout
            if on_event is not None:
                on_event(evt)
            events.append(evt)
            if evt.get("event") == "run_status" and evt.get("status") in _TERMINAL_STATUSES:
                return events
        raise TimeoutError(
            f"run {run_id} did not reach terminal status — no events received for {idle_timeout}s"
        )
