"""Per-conversation transaction owner and lifecycle admission."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from agent.core.types import Message, TurnResult
from agent.core.agent.compaction.types import CompactionResult

from .context_state import MemorySnapshot, SessionFileState
from .transcript import JsonlTranscript
from .types import (
    AppendMessageResult,
    ConversationClosed,
    ExternalMessage,
    PromptSlotSeed,
    SessionConfig,
    SessionRef,
    TurnRequest,
)
from .models import Session


@dataclass(slots=True)
class ConversationState:
    """Hold all mutable context that belongs to one conversation identity."""

    ref: SessionRef
    config: SessionConfig
    history: list[Message]
    prompt_seed: PromptSlotSeed
    transcript: JsonlTranscript
    file_state: SessionFileState
    memory_snapshot: MemorySnapshot | None = None
    active_model: str | None = None


@dataclass(frozen=True, slots=True)
class ForkSnapshot:
    """Capture one source view for independent re-stamping into a new session."""

    config: SessionConfig
    messages: tuple[Message, ...]
    prompt_seed: PromptSlotSeed


class ForkDirectory(Protocol):
    """Create a child conversation from one captured source view."""

    async def fork_from(
        self, source: ConversationSession, *, up_to: str | None
    ) -> tuple[Session, dict[str, str]]:
        """Create and return a fork plus source-to-target message ids."""


class ConversationEngine(Protocol):
    """Execute agent algorithms against one already-bound conversation state."""

    async def execute_turn(
        self, state: ConversationState, request: TurnRequest
    ) -> TurnResult:
        """Execute one serialized turn without owning session identity or storage."""

    async def compact(self, state: ConversationState) -> CompactionResult | None:
        """Compute and commit one manual compaction for a bound state."""


class _LifecycleState(StrEnum):
    OPEN = "open"
    DRAINING = "draining"
    CLOSED = "closed"


class _OperationPermit:
    def __init__(self, gate: _LifecyclePermitGate) -> None:
        self._gate = gate
        self._released = False

    def __enter__(self) -> _OperationPermit:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._gate.release()


class _LifecyclePermitGate:
    """Linearize operation admission with conversation close."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._state = _LifecycleState.OPEN
        self._active = 0

    def begin_operation(self) -> _OperationPermit:
        """Admit one operation or fail after draining has begun."""

        with self._condition:
            if self._state is not _LifecycleState.OPEN:
                raise ConversationClosed("conversation is closing or closed")
            self._active += 1
        return _OperationPermit(self)

    def release(self) -> None:
        with self._condition:
            if self._active <= 0:
                raise RuntimeError("conversation operation permit underflow")
            self._active -= 1
            if self._active == 0:
                self._condition.notify_all()

    def begin_draining(self) -> bool:
        """Close admission exactly once and report whether this caller won."""

        with self._condition:
            if self._state is _LifecycleState.CLOSED:
                return False
            if self._state is _LifecycleState.DRAINING:
                return False
            self._state = _LifecycleState.DRAINING
            self._condition.notify_all()
            return True

    def wait_for_drain(self) -> None:
        """Block a worker until every previously admitted operation exits."""

        with self._condition:
            while self._active:
                self._condition.wait()

    def mark_closed(self) -> None:
        with self._condition:
            self._state = _LifecycleState.CLOSED
            self._condition.notify_all()


class ConversationSession:
    """Own one session's state, transcript, turn serialization, and close ordering."""

    def __init__(
        self,
        *,
        ref: SessionRef,
        transcript: JsonlTranscript,
        engine: ConversationEngine,
    ) -> None:
        if transcript.ref != ref:
            raise ValueError("conversation and transcript must share one SessionRef")
        self._ref = ref
        self._transcript = transcript
        self._engine = engine
        self._lifecycle = _LifecyclePermitGate()
        self._turn_gate = asyncio.Lock()
        self._load_gate = asyncio.Lock()
        self._close_gate = asyncio.Lock()
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self._state: ConversationState | None = None
        self._state_guard = threading.Lock()
        self._fork_directory: ForkDirectory | None = None

    @property
    def ref(self) -> SessionRef:
        """Return this conversation's immutable canonical address."""

        return self._ref

    @property
    def prompt_seed(self) -> PromptSlotSeed:
        """Return the rehydrated seed after materialization, or empty before it."""

        with self._state_guard:
            return (
                self._state.prompt_seed if self._state is not None else PromptSlotSeed()
            )

    @property
    def external_epoch(self) -> int:
        """Return the transcript's monotonic committed external append epoch."""

        return self._transcript.external_epoch

    async def submit_turn(self, request: TurnRequest) -> TurnResult:
        """Execute one turn under lifecycle admission and per-session serialization."""

        self._bind_owner_loop()
        with self._lifecycle.begin_operation():
            async with self._turn_gate:
                state = await self._ensure_loaded()
                state.active_model = request.model
                try:
                    return await self._engine.execute_turn(state, request)
                finally:
                    state.active_model = None

    def append_external(self, request: ExternalMessage) -> AppendMessageResult:
        """Durably append a message without holding the long-lived turn gate."""

        with self._lifecycle.begin_operation():
            result = self._transcript.append_external(request)
            if result.created:
                loaded = self._transcript.load()
                with self._state_guard:
                    if self._state is not None:
                        self._state.history = loaded.messages
            return result

    def history_snapshot(self) -> tuple[Message, ...]:
        """Return an immutable diagnostic snapshot of the loaded reachable history."""

        with self._state_guard:
            if self._state is not None:
                return tuple(self._state.history)
        return tuple(self._transcript.load().messages)

    async def compact(self) -> CompactionResult | None:
        """Run manual compaction in the same transaction domain as turns."""

        self._bind_owner_loop()
        with self._lifecycle.begin_operation():
            async with self._turn_gate:
                state = await self._ensure_loaded()
                return await self._engine.compact(state)

    async def fork(self, *, up_to: str | None = None) -> tuple[Session, dict[str, str]]:
        """Fork this conversation through its identity-owning directory."""

        self._bind_owner_loop()
        directory = self._fork_directory
        if directory is None:
            raise RuntimeError("conversation is not bound to a SessionDirectory")
        with self._lifecycle.begin_operation():
            return await directory.fork_from(self, up_to=up_to)

    async def capture_fork(self, *, up_to: str | None) -> ForkSnapshot:
        """Capture a durable whole or point-in-time transcript view."""

        if up_to is not None:
            loaded = await asyncio.to_thread(self._transcript.load, up_to=up_to)
            return ForkSnapshot(
                config=loaded.config,
                messages=tuple(loaded.messages),
                prompt_seed=loaded.prompt_seed,
            )
        async with self._turn_gate:
            await self._ensure_loaded()
            loaded = await asyncio.to_thread(self._transcript.load)
            return ForkSnapshot(
                config=loaded.config,
                messages=tuple(loaded.messages),
                prompt_seed=loaded.prompt_seed,
            )

    async def close(self) -> None:
        """Stop admission, drain admitted work, flush, and close deterministically."""

        self._bind_owner_loop()
        async with self._close_gate:
            if not self._lifecycle.begin_draining():
                return
            await asyncio.to_thread(self._lifecycle.wait_for_drain)
            await asyncio.shield(self._transcript.flush_async())
            with self._state_guard:
                self._state = None
            self._lifecycle.mark_closed()

    async def _ensure_loaded(self) -> ConversationState:
        with self._state_guard:
            if self._state is not None:
                return self._state
        async with self._load_gate:
            with self._state_guard:
                if self._state is not None:
                    return self._state
            await asyncio.to_thread(self._transcript.prepare_for_run)
            loaded = await asyncio.to_thread(self._transcript.load)
            state = ConversationState(
                ref=self._ref,
                config=loaded.config,
                history=loaded.messages,
                prompt_seed=loaded.prompt_seed,
                transcript=self._transcript,
                file_state=SessionFileState(),
            )
            with self._state_guard:
                self._state = state
            return state

    def _bind_owner_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._owner_loop is None:
            self._owner_loop = loop
            return
        if self._owner_loop is not loop:
            raise RuntimeError("conversation async operations require one owner loop")

    def _bind_fork_directory(self, directory: ForkDirectory) -> None:
        if self._fork_directory is not None and self._fork_directory is not directory:
            raise RuntimeError("conversation is already bound to another directory")
        self._fork_directory = directory

    def _install_fork_snapshot(self, messages: tuple[Message, ...]) -> None:
        """Persist a Directory-owned, re-stamped fork snapshot before publication."""

        self._transcript.append_messages_snapshot(messages)
