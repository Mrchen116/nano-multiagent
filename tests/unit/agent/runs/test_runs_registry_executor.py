import asyncio
import threading
import time
from pathlib import Path

from agent.core.llm.interfaces import LLMMessage
from agent.core.errors import CompactionError
from agent.core.runs.executor import KernelExecutor
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.types import NewSession, TurnRequest
from agent.core.types import Message, TurnResult


class _Conversation:
    def __init__(
        self,
        *,
        ref,
        transcript,
        block_until_abort: bool = False,
        block_requests: set[int] | None = None,
    ) -> None:
        self.ref = ref
        self.transcript = transcript
        self.block_until_abort = block_until_abort
        self.block_requests = block_requests or ({1} if block_until_abort else set())
        self.requests: list[TurnRequest] = []
        self.started = threading.Event()

    async def submit_turn(self, request: TurnRequest) -> TurnResult:
        self.requests.append(request)
        self.started.set()
        if len(self.requests) in self.block_requests:
            while request.controller is not None and not request.controller.is_aborted:
                await asyncio.sleep(0.005)
        text = str(request.parts[-1].get("text", ""))
        return TurnResult(
            session_id=self.ref.session_id,
            turn_id=f"turn_{len(self.requests)}",
            messages=(
                Message(message_id="msg_result", role="assistant", content=text),
            ),
            completed=True,
            stop_reason="aborted"
            if request.controller is not None and request.controller.is_aborted
            else "completed",
        )

    async def close(self) -> None:
        return None


class _FailingConversation(_Conversation):
    def __init__(self, *, error: Exception, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.error = error

    async def submit_turn(self, request: TurnRequest) -> TurnResult:
        raise self.error


def _wait_for(predicate, timeout: float = 1.0) -> None:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def test_registry_is_semantic_writer_while_executor_owns_cleanup(
    tmp_path: Path,
) -> None:
    conversations: list[_Conversation] = []

    def factory(ref, transcript):  # noqa: ANN001, ANN202
        conversation = _Conversation(ref=ref, transcript=transcript)
        conversations.append(conversation)
        return conversation

    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=factory,
    )
    session = directory.create(NewSession(workspace_root=tmp_path))
    executor = KernelExecutor()
    registry = RunsRegistry(directory=directory, executor=executor)

    submitted = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "hello"}],
        model="test:model",
    )

    _wait_for(lambda: registry.get(submitted.run_id).status is RunStatus.COMPLETED)
    completed = registry.get(submitted.run_id)
    assert completed is not None
    assert completed.output_text == "hello"
    assert conversations[0].requests[0].model == "test:model"
    _wait_for(lambda: executor.active_target_count == 0)
    registry.shutdown()


def _run_failed_record(tmp_path: Path, error: Exception):  # noqa: ANN201
    def factory(ref, transcript):  # noqa: ANN001, ANN202
        return _FailingConversation(ref=ref, transcript=transcript, error=error)

    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=factory,
    )
    session = directory.create(NewSession(workspace_root=tmp_path))
    executor = KernelExecutor()
    registry = RunsRegistry(directory=directory, executor=executor)
    submitted = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "fail"}],
    )
    _wait_for(lambda: registry.get(submitted.run_id).status is RunStatus.FAILED)
    record = registry.get(submitted.run_id)
    registry.shutdown()
    assert record is not None
    return record


def test_registry_preserves_only_typed_compaction_error_payload(tmp_path: Path) -> None:
    compaction = CompactionError(
        trigger="overflow",
        failure_kind="summary",
        consecutive_failures=1,
        overflow_cause=RuntimeError("maximum context length exceeded"),
    )

    typed = _run_failed_record(tmp_path / "typed", compaction)
    ordinary = _run_failed_record(tmp_path / "ordinary", RuntimeError("boom"))

    assert typed.error == compaction.to_dict()
    assert ordinary.error == {"code": "run_execution_failed", "message": "boom"}


def test_interrupt_parks_pending_synchronously_before_next_submit(
    tmp_path: Path,
) -> None:
    conversations: list[_Conversation] = []

    def factory(ref, transcript):  # noqa: ANN001, ANN202
        conversation = _Conversation(
            ref=ref,
            transcript=transcript,
            block_until_abort=not conversations,
        )
        conversations.append(conversation)
        return conversation

    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=factory,
    )
    session = directory.create(NewSession(workspace_root=tmp_path))
    executor = KernelExecutor()
    registry = RunsRegistry(directory=directory, executor=executor)
    first = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "first"}],
    )
    assert conversations[0].started.wait(timeout=1)
    assert registry.inject_pending_message(
        session.ref.session_id,
        LLMMessage(
            role="user",
            content=[
                {"type": "text", "text": "steered"},
                {"type": "image", "image_url": "data:image/png;base64,AAAA"},
            ],
        ),
    )

    assert registry.interrupt(session.ref.session_id) == first.run_id
    assert registry._held_pending[first.session_id][0].message.content == [
        {"type": "text", "text": "steered"},
        {"type": "image", "image_url": "data:image/png;base64,AAAA"},
    ]
    _wait_for(lambda: registry.get(first.run_id).status is RunStatus.CANCELLED)
    second = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "second"}],
    )
    _wait_for(lambda: registry.get(second.run_id).status is RunStatus.COMPLETED)
    assert list(conversations[0].requests[-1].parts) == [
        {"type": "text", "text": "steered"},
        {"type": "image", "image_url": "data:image/png;base64,AAAA"},
        {"type": "text", "text": "second"},
    ]
    registry.shutdown()


def test_non_user_terminal_continuation_preserves_structured_pending_parts(
    tmp_path: Path,
) -> None:
    """A stranded image steer must survive an abnormal non-user terminal."""

    conversations: list[_Conversation] = []

    def factory(ref, transcript):  # noqa: ANN001, ANN202
        conversation = _Conversation(
            ref=ref,
            transcript=transcript,
            block_until_abort=not conversations,
        )
        conversations.append(conversation)
        return conversation

    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=factory,
    )
    session = directory.create(NewSession(workspace_root=tmp_path))
    executor = KernelExecutor()
    registry = RunsRegistry(directory=directory, executor=executor)
    first = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "first"}],
    )
    assert conversations[0].started.wait(timeout=1)
    assert registry.inject_pending_message(
        session.ref.session_id,
        LLMMessage(
            role="user",
            content=[
                {"type": "text", "text": "continue with image"},
                {"type": "image", "image_url": "data:image/png;base64,BBBB"},
            ],
        ),
    )

    registry._controllers[first.run_id].abort()  # noqa: SLF001
    _wait_for(lambda: len(conversations[0].requests) == 2)

    assert list(conversations[0].requests[-1].parts) == [
        {"type": "text", "text": "continue with image"},
        {"type": "image", "image_url": "data:image/png;base64,BBBB"},
    ]
    registry.shutdown()


def test_expected_run_injection_never_targets_replacement_active_run(
    tmp_path: Path,
) -> None:
    """A stale run marker must not inject into its session's replacement run."""

    conversations: list[_Conversation] = []

    def factory(ref, transcript):  # noqa: ANN001, ANN202
        conversation = _Conversation(
            ref=ref,
            transcript=transcript,
            block_requests={2},
        )
        conversations.append(conversation)
        return conversation

    directory = SessionDirectory(
        files=JsonlSessionFiles(data_dir=tmp_path / "data"),
        writer=JsonlWriter(),
        conversation_factory=factory,
    )
    session = directory.create(NewSession(workspace_root=tmp_path))
    executor = KernelExecutor()
    registry = RunsRegistry(directory=directory, executor=executor)
    first = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "first"}],
    )
    _wait_for(lambda: registry.get(first.run_id).status is RunStatus.COMPLETED)
    second = registry.submit(
        session_id=session.ref.session_id,
        workspace_root=tmp_path,
        parts=[{"type": "text", "text": "second"}],
    )
    _wait_for(lambda: registry.get(second.run_id).status is RunStatus.RUNNING)

    assert not registry.inject_pending_message(
        session.ref.session_id,
        LLMMessage(role="user", content="must-not-reach-second"),
        expected_run_id=first.run_id,
    )
    assert registry.inject_pending_message(
        session.ref.session_id,
        LLMMessage(role="user", content="belongs-to-second"),
        expected_run_id=second.run_id,
    )

    assert registry.interrupt(session.ref.session_id) == second.run_id
    assert [
        item.message.content for item in registry._held_pending[second.session_id]
    ] == ["belongs-to-second"]
    registry.shutdown()
