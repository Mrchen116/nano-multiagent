"""Background queue runner for REPL async message dispatch."""

from dataclasses import dataclass
from queue import Queue
from threading import Lock, Thread
from typing import Callable


@dataclass(frozen=True, slots=True)
class QueuedReplMessage:
    """One queued REPL send task scoped to a concrete session."""

    session_id: str
    text: str


class ReplRunQueue:
    """Serialize REPL sends on a worker thread while input loop stays responsive."""

    def __init__(
        self,
        *,
        process_message: Callable[[QueuedReplMessage], None],
        on_worker_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._process_message = process_message
        self._on_worker_error = on_worker_error
        self._queue: Queue[QueuedReplMessage | None] = Queue()
        self._state_lock = Lock()
        self._active = False
        self._closed = False
        self._worker = Thread(target=self._run, name="nano-cli-repl-run-queue", daemon=True)
        self._worker.start()

    def enqueue(self, *, session_id: str, text: str) -> int:
        """Enqueue one message and return backlog size before enqueue.

        Return value semantics:
        - `0`: no backlog before enqueue (message can start immediately).
        - `>=1`: number of runs/messages ahead of this item.
        """
        with self._state_lock:
            if self._closed:
                raise RuntimeError("repl run queue is closed")
            backlog_before = self._queue.qsize() + (1 if self._active else 0)
            self._queue.put(QueuedReplMessage(session_id=session_id, text=text))
            return backlog_before

    def backlog_size(self) -> int:
        """Return approximate number of active+queued items."""
        with self._state_lock:
            return self._queue.qsize() + (1 if self._active else 0)

    def close(self, *, wait_for_drain: bool) -> None:
        """Close worker and optionally wait for all queued messages to finish."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        if wait_for_drain:
            self._queue.join()
        self._queue.put(None)
        self._worker.join()

    def wait_for_drain(self) -> None:
        """Block until active/queued work is fully drained."""
        self._queue.join()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            with self._state_lock:
                self._active = True
            try:
                self._process_message(item)
            except Exception as exc:  # pragma: no cover - defensive worker boundary
                if self._on_worker_error is not None:
                    self._on_worker_error(exc)
            finally:
                with self._state_lock:
                    self._active = False
                self._queue.task_done()
