"""Per-run control plane: abort signal and pending message injection queue."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin


@dataclass(frozen=True)
class PendingMessage:
    """One round-boundary injection: the message plus the origin that produced it.

    The origin travels with the message so the terminal-path stranded-continuation
    re-run (RunsRegistry) attributes the right source — a user mid-run steer must
    continue as RunOrigin.USER, not the hardcoded BACKGROUND_TASK (bugfix-426 决策3).
    """

    message: "LLMMessage"
    origin: "RunOrigin"


@dataclass
class RunController:
    """
    Control channel for one agent run.

    Writers: RunsRegistry (via abort / enqueue_message)
    Readers: AgentLoop (via is_aborted / drain_pending, read-only)

    Thread safety: both threading.Event and queue.SimpleQueue are safe to write
    from HTTP-handler threads and read from worker-thread event loops.
    """

    cancel_event: threading.Event = field(default_factory=threading.Event)
    abort_event: threading.Event = field(default_factory=threading.Event)
    # Set when the interrupt was initiated by the user (/stop, CLI Ctrl-C) rather
    # than by a system watchdog / crash. Distinguishes the orphaned tool_call
    # recovery content: user → "[Request interrupted by user for tool use]"
    # (CC-identical, so the model knows to stop and wait), system → "[interrupted]"
    # (bugfix-417-M5, #114). Badge stays "已中断" in both cases.
    user_interrupt_event: threading.Event = field(default_factory=threading.Event)
    _pending: queue.SimpleQueue = field(default_factory=queue.SimpleQueue)
    # bugfix-426-M4 决策5: the terminal lock makes "the loop re-drains at its terminal
    # decision and commits the run as finished" and "the registry injects a steer"
    # mutually exclusive, so a steer can never be stranded in the window between the
    # last round-boundary drain and the break (the #140 carrier of a continuation
    # new run_id). Either the inject wins (loop sees it on re-drain and continues the
    # SAME run) or the commit wins (inject returns False; the caller falls back to a
    # new run). The SimpleQueue is thread-safe per put/get; this lock adds the
    # cross-operation atomicity the queue alone cannot give.
    _terminal_lock: threading.Lock = field(default_factory=threading.Lock)
    _terminal_committed: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        """Signal pre-turn cancellation (run not yet started). Idempotent."""
        self.cancel_event.set()

    def abort(self, *, user_initiated: bool = False) -> None:
        """Signal force interrupt (run is executing). Idempotent.

        Args:
            user_initiated: True when triggered by an explicit user /stop or
                CLI Ctrl-C, so the recovery content attributes the interrupt to
                the user (bugfix-417-M5, #114).
        """
        if user_initiated:
            self.user_interrupt_event.set()
        self.abort_event.set()

    def enqueue_message(self, message: "LLMMessage", origin: "RunOrigin") -> bool:
        """Enqueue a message for round-boundary injection. Thread-safe.

        Args:
            message: The message to inject before the next LLM call.
            origin: Source that produced this message (e.g. RunOrigin.USER for a
                mid-run steer, RunOrigin.BACKGROUND_TASK for a task notification).
                Carried so a stranded continuation re-run keeps the right origin.

        Returns:
            True if the message was enqueued; False if the run has already committed
            its terminal (the loop decided to finish and will not drain again), in
            which case the caller must route this message to a new run instead of
            losing it (bugfix-426-M4 决策5).
        """
        with self._terminal_lock:
            if self._terminal_committed.is_set():
                return False
            self._pending.put_nowait(PendingMessage(message=message, origin=origin))
            return True

    def try_commit_terminal(self) -> list[PendingMessage]:
        """At the loop's terminal decision, atomically re-check for pending messages.

        Holds the terminal lock so this re-drain cannot interleave with a concurrent
        ``enqueue_message`` (bugfix-426-M4 决策5). Two outcomes:

        - Pending is **non-empty**: a steer arrived in the terminal window. Return the
          drained messages WITHOUT committing — the caller (AgentLoop) appends them to
          context and continues the SAME run. The run stays live, so later injects keep
          succeeding.
        - Pending is **empty**: nothing to consume. Commit the terminal (set the flag)
          so any subsequent ``enqueue_message`` is rejected (returns False) and routed
          to a new run. Return an empty list — the caller breaks out of the loop.
        """
        with self._terminal_lock:
            drained = self._drain_locked()
            if drained:
                return drained
            self._terminal_committed.set()
            return []

    def commit_terminal(self) -> None:
        """Unconditionally commit the run's terminal — a HARD stop with no re-drain.

        bugfix-426-M4 V1: the loop has several terminal exits. The normal-completion
        exit can absorb a late steer by re-looping (``try_commit_terminal``). But the
        HARD-stop exits — ``max_turns`` (already at the round cap) and
        ``tool_registry_unavailable`` (cannot run another round) and a user abort —
        cannot continue; re-looping there would carry the steer into ``llm_messages``
        only to exit at the top of the loop before the next LLM call, silently dropping
        it. So those exits commit the terminal unconditionally: any inject racing AFTER
        this point is rejected (``enqueue_message`` returns False) and the caller routes
        it to a fresh run (``injected=False``), which the relay anchors cleanly — never
        stranded into a continuation whose events the relay would drop (the #140 class
        of bug, here at the hard-stop exits). A steer already enqueued BEFORE this
        commit (a vanishingly narrow window — both ops hold ``_terminal_lock``) still
        survives via the registry's terminal chokepoint. Idempotent.
        """
        with self._terminal_lock:
            self._terminal_committed.set()

    def drain_pending(self) -> list[PendingMessage]:
        """Drain and return all pending messages in FIFO order. Non-blocking."""
        return self._drain_locked()

    def _drain_locked(self) -> list[PendingMessage]:
        msgs: list[PendingMessage] = []
        while True:
            try:
                msgs.append(self._pending.get_nowait())
            except queue.Empty:
                return msgs

    @property
    def is_terminal_committed(self) -> bool:
        """True once the run committed its terminal (no further injection accepted)."""
        return self._terminal_committed.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    @property
    def is_aborted(self) -> bool:
        return self.abort_event.is_set()

    @property
    def is_user_interrupt(self) -> bool:
        """True when the abort was initiated by an explicit user /stop / Ctrl-C."""
        return self.user_interrupt_event.is_set()
