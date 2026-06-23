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

    def enqueue_message(self, message: "LLMMessage", origin: "RunOrigin") -> None:
        """Enqueue a message for round-boundary injection. Thread-safe.

        Args:
            message: The message to inject before the next LLM call.
            origin: Source that produced this message (e.g. RunOrigin.USER for a
                mid-run steer, RunOrigin.BACKGROUND_TASK for a task notification).
                Carried so a stranded continuation re-run keeps the right origin.
        """
        self._pending.put_nowait(PendingMessage(message=message, origin=origin))

    def drain_pending(self) -> list[PendingMessage]:
        """Drain and return all pending messages in FIFO order. Non-blocking."""
        msgs: list[PendingMessage] = []
        while True:
            try:
                msgs.append(self._pending.get_nowait())
            except queue.Empty:
                return msgs

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
