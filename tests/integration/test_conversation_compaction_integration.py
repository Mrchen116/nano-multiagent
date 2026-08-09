import asyncio
import threading
from pathlib import Path
from typing import Any

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.types import SessionRef
from agent.core.types import TokenUsage
from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel


COMPACTION_FAILURE_TEXT = (
    "上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。"
    "请稍后重试，或发送 /compact <希望保留的重点> 后继续。"
)


def _is_summary_request(request: LLMGenerateRequest) -> bool:
    return request.tools == ()


def _compaction_llm() -> LLMConfig:
    model = LLMModel(name="threshold-model", context_window=30_000)
    return LLMConfig(
        provider="openai_compat",
        model=model.name,
        base_url="http://127.0.0.1:4000",
        default_model=model.name,
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(model,),
            ),
        ),
    )


async def _wait_for_terminal(kernel, run_id: str, *, timeout: float = 3.0):  # noqa: ANN001, ANN201
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


async def _submit_and_collect(kernel, session_id: str, workspace: Path, text: str):  # noqa: ANN001, ANN201
    run = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=workspace,
    )
    events: list[dict[str, Any]] = []
    async for event in kernel.stream(session_id, after_sequence=run.start_sequence):
        if event.get("run_id") != run.run_id:
            continue
        events.append(event)
        if event.get("event") == "run_status" and event.get("status") in {
            "completed",
            "failed",
            "cancelled",
        }:
            break
    record = kernel.get_run(run.run_id)
    assert record is not None
    return record, events


def _assert_compaction_prompt_before_failed(events: list[dict[str, Any]]) -> None:
    prompt_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "assistant_message"
        and event.get("content") == COMPACTION_FAILURE_TEXT
    )
    failed_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "run_status" and event.get("status") == "failed"
    )
    assert prompt_index < failed_index


def _terminal_error(events: list[dict[str, Any]]) -> dict[str, Any]:
    return next(
        event["error"]
        for event in events
        if event.get("event") == "run_status" and event.get("status") == "failed"
    )


def _request_text(request: LLMGenerateRequest) -> str:
    return "\n".join(str(message.content) for message in request.messages)


async def test_threshold_compaction_replaces_live_history_for_next_turn(
    tmp_path: Path,
) -> None:
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(
                    role="assistant", content="<summary>COMPACTED-CONTEXT</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(role="assistant", content=f"reply-{len(normal_requests)}")
            prompt_tokens = 10_000 if len(normal_requests) == 1 else 100
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=10,
                    total_tokens=prompt_tokens + 10,
                ),
            )

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        for text in ("old-context", "triggers-threshold"):
            run = kernel.submit(
                session_id=session.session_id,
                parts=[{"type": "text", "text": text}],
                workspace_root=tmp_path,
            )
            assert (await _wait_for_terminal(kernel, run.run_id)).status == "completed"

        followup = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "after-compaction"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, followup.run_id)).status == "completed"

        context = _request_text(normal_requests[-1])
        assert "COMPACTED-CONTEXT" in context
        assert "old-context" not in context
    finally:
        kernel.close()


async def test_threshold_compaction_rejects_stale_external_epoch(
    tmp_path: Path,
) -> None:
    summary_started = threading.Event()
    release_summary = threading.Event()
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                summary_started.set()
                await asyncio.to_thread(release_summary.wait)
                yield LLMMessage(
                    role="assistant", content="<summary>STALE-SUMMARY</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(role="assistant", content="ack")
            prompt_tokens = 10_000 if len(normal_requests) == 1 else 100
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=10,
                    total_tokens=prompt_tokens + 10,
                ),
            )

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "seed-threshold"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, first.run_id)).status == "completed"

        compacting = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "start-summary"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(summary_started.wait, 2)
        kernel.append_message(
            session.session_id,
            role="user",
            content="external-during-summary",
            workspace_root=tmp_path,
        )
        release_summary.set()
        assert (
            await _wait_for_terminal(kernel, compacting.run_id)
        ).status == "completed"

        followup = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "after-stale-summary"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, followup.run_id)).status == "completed"
        assert "external-during-summary" in _request_text(normal_requests[-1])
    finally:
        release_summary.set()
        kernel.close()


async def test_manual_compaction_refreshes_agents_md_prompt(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("PROMPT-MARKER-OLD", encoding="utf-8")
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(
                    role="assistant", content="<summary>MANUAL-COMPACT</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(role="assistant", content="ack")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "freeze prompt"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, first.run_id)).status == "completed"
        assert "PROMPT-MARKER-OLD" in _request_text(normal_requests[-1])

        agents_md.write_text("PROMPT-MARKER-NEW", encoding="utf-8")
        frozen = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "still frozen"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, frozen.run_id)).status == "completed"
        frozen_prompt = _request_text(normal_requests[-1])
        assert "PROMPT-MARKER-OLD" in frozen_prompt
        assert "PROMPT-MARKER-NEW" not in frozen_prompt

        assert (
            await kernel.compact(session.session_id, workspace_root=tmp_path)
            is not None
        )

        second = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "refresh prompt"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, second.run_id)).status == "completed"
        refreshed = _request_text(normal_requests[-1])
        assert "PROMPT-MARKER-NEW" in refreshed
        assert "PROMPT-MARKER-OLD" not in refreshed
    finally:
        kernel.close()


async def test_overflow_compaction_retries_and_reopens_from_jsonl(
    tmp_path: Path,
) -> None:
    class _OverflowClient:
        def __init__(self) -> None:
            self.normal_calls = 0
            self.summary_calls = 0
            self.overflow_raised = False

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                self.summary_calls += 1
                yield LLMMessage(
                    role="assistant", content="<summary>OVERFLOW-REPLAY</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            self.normal_calls += 1
            if self.normal_calls == 2:
                self.overflow_raised = True
                raise ModelError(
                    "context overflow",
                    details={
                        "status_code": 400,
                        "response": "maximum context length exceeded",
                    },
                )
            yield LLMMessage(
                role="assistant",
                content="retry-ok",
                finish_reason="stop",
            )

    first_client = _OverflowClient()
    first_kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=first_client,
    )
    session_id = ""
    try:
        session = await first_kernel.create_session(workspace_root=tmp_path)
        session_id = session.session_id
        for text in ("first", "overflow-now"):
            run = first_kernel.submit(
                session_id=session_id,
                parts=[{"type": "text", "text": text}],
                workspace_root=tmp_path,
            )
            assert (await _wait_for_terminal(first_kernel, run.run_id)).status == (
                "completed"
            )
        assert first_client.overflow_raised
        assert first_client.summary_calls == 1
        assert first_client.normal_calls == 3
    finally:
        first_kernel.close()

    reopened_requests: list[LLMGenerateRequest] = []

    class _ReopenedClient:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            reopened_requests.append(request)
            yield LLMMessage(role="assistant", content="reopened", finish_reason="stop")

    second_kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_ReopenedClient(),
    )
    try:
        continued = second_kernel.submit(
            session_id=session_id,
            parts=[{"type": "text", "text": "after-restart"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(second_kernel, continued.run_id)).status == (
            "completed"
        )
        assert "OVERFLOW-REPLAY" in _request_text(reopened_requests[-1])
    finally:
        second_kernel.close()


async def test_threshold_summary_failure_stops_on_third_attempt_without_boundary(
    tmp_path: Path,
) -> None:
    class _Client:
        def __init__(self) -> None:
            self.summary_calls = 0

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                self.summary_calls += 1
                yield LLMMessage(role="assistant", content="")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            yield LLMMessage(role="assistant", content="continued")
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(10_000, 10, 10_010),
            )

    client = _Client()
    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        for text in ("seed", "failure-one", "failure-two"):
            record, _events = await _submit_and_collect(
                kernel, session.session_id, tmp_path, text
            )
            assert record.status == "completed"

        failed, events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "failure-three"
        )

        assert failed.status == "failed"
        assert _terminal_error(events) == {
            "code": "compaction_failed",
            "message": "context compaction failed",
            "retryable": True,
            "details": {
                "trigger": "threshold",
                "failure_kind": "summary",
                "consecutive_failures": 3,
            },
        }
        assert client.summary_calls == 3
        _assert_compaction_prompt_before_failed(events)
        transcript = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript
        assert not any(
            entry.__class__.__name__ == "CompactionEntry"
            for entry in transcript.list_event_entries()
        )
        assert COMPACTION_FAILURE_TEXT not in {
            message.content for message in transcript.load().messages
        }
    finally:
        kernel.close()


async def test_overflow_summary_failure_stops_without_retry_or_boundary(
    tmp_path: Path,
) -> None:
    class _Client:
        def __init__(self) -> None:
            self.normal_calls = 0
            self.summary_calls = 0

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                self.summary_calls += 1
                yield LLMMessage(role="assistant", content="")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            self.normal_calls += 1
            if self.normal_calls == 2:
                raise ModelError(
                    "context overflow",
                    details={"response": "maximum context length exceeded"},
                )
            yield LLMMessage(role="assistant", content="seeded")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    client = _Client()
    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        seeded, _events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "seed"
        )
        assert seeded.status == "completed"

        failed, events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "overflow-now"
        )

        assert failed.status == "failed"
        assert _terminal_error(events) == {
            "code": "compaction_failed",
            "message": "context compaction failed",
            "retryable": True,
            "details": {
                "trigger": "overflow",
                "failure_kind": "summary",
                "consecutive_failures": 1,
                "overflow_cause": {
                    "code": "model_error",
                    "message": "context overflow",
                    "retryable": True,
                    "details": {"response": "maximum context length exceeded"},
                },
            },
        }
        assert client.normal_calls == 2
        assert client.summary_calls == 1
        _assert_compaction_prompt_before_failed(events)
        transcript = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript
        assert not any(
            entry.__class__.__name__ == "CompactionEntry"
            for entry in transcript.list_event_entries()
        )
        assert COMPACTION_FAILURE_TEXT not in {
            message.content for message in transcript.load().messages
        }
    finally:
        kernel.close()


async def test_threshold_persistence_failure_is_visible_and_atomic(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    class _Client:
        def __init__(self) -> None:
            self.normal_calls = 0

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(role="assistant", content="durable summary")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            self.normal_calls += 1
            yield LLMMessage(role="assistant", content="continued")
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(10_000, 10, 10_010),
            )

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        seeded, _events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "seed"
        )
        assert seeded.status == "completed"
        transcript = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript
        before = transcript._path.read_bytes()  # noqa: SLF001

        def _fail_append(**_kwargs):  # noqa: ANN003, ANN202
            raise OSError("disk unavailable")

        monkeypatch.setattr(transcript, "append_compaction", _fail_append)
        failed, events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "persist-failure"
        )

        assert failed.status == "failed"
        assert _terminal_error(events) == {
            "code": "compaction_failed",
            "message": "context compaction failed",
            "retryable": True,
            "details": {
                "trigger": "threshold",
                "failure_kind": "persistence",
                "consecutive_failures": 0,
                "cause": {"type": "OSError", "message": "disk unavailable"},
            },
        }
        _assert_compaction_prompt_before_failed(events)
        assert transcript._path.read_bytes() != before  # current user turn is durable
        assert not any(
            entry.__class__.__name__ == "CompactionEntry"
            for entry in transcript.list_event_entries()
        )
        assert COMPACTION_FAILURE_TEXT not in {
            message.content for message in transcript.load().messages
        }
    finally:
        kernel.close()


async def test_overflow_persistence_failure_preserves_both_causes(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    class _Client:
        def __init__(self) -> None:
            self.normal_calls = 0

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(role="assistant", content="summary")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            self.normal_calls += 1
            if self.normal_calls == 2:
                raise ModelError(
                    "context overflow",
                    details={"response": "maximum context length exceeded"},
                )
            yield LLMMessage(role="assistant", content="seeded")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    kernel = build_kernel(
        llm=_compaction_llm(), repo_root=tmp_path, _llm_client_override=_Client()
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        seeded, _events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "seed"
        )
        assert seeded.status == "completed"
        transcript = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript

        def _fail_append(**_kwargs):  # noqa: ANN003, ANN202
            raise OSError("disk unavailable")

        monkeypatch.setattr(transcript, "append_compaction", _fail_append)
        failed, events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "overflow"
        )

        terminal_error = _terminal_error(events)
        assert terminal_error["code"] == "compaction_failed"
        assert terminal_error["details"] == {
            "trigger": "overflow",
            "failure_kind": "persistence",
            "consecutive_failures": 0,
            "cause": {"type": "OSError", "message": "disk unavailable"},
            "overflow_cause": {
                "code": "model_error",
                "message": "context overflow",
                "retryable": True,
                "details": {"response": "maximum context length exceeded"},
            },
        }
        _assert_compaction_prompt_before_failed(events)
    finally:
        kernel.close()


async def test_overflow_stale_commit_keeps_original_error_and_does_not_count(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    class _Client:
        def __init__(self) -> None:
            self.normal_calls = 0
            self.summary_calls = 0

        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                self.summary_calls += 1
                content = "stale summary" if self.summary_calls == 1 else ""
                yield LLMMessage(role="assistant", content=content)
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            self.normal_calls += 1
            if self.normal_calls >= 2:
                raise ModelError(
                    "context overflow",
                    details={"response": "maximum context length exceeded"},
                )
            yield LLMMessage(role="assistant", content="seeded")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    client = _Client()
    kernel = build_kernel(
        llm=_compaction_llm(), repo_root=tmp_path, _llm_client_override=client
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        seeded, _events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "seed"
        )
        assert seeded.status == "completed"
        transcript = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session.session_id, workspace_root=tmp_path)
        )._transcript
        original_append = transcript.append_compaction
        monkeypatch.setattr(transcript, "append_compaction", lambda **_kwargs: False)

        stale, stale_events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "stale-overflow"
        )

        assert _terminal_error(stale_events) == {
            "code": "run_execution_failed",
            "message": "context overflow",
        }
        assert not any(
            event.get("content") == COMPACTION_FAILURE_TEXT for event in stale_events
        )

        monkeypatch.setattr(transcript, "append_compaction", original_append)
        failed, events = await _submit_and_collect(
            kernel, session.session_id, tmp_path, "summary-failure"
        )

        assert _terminal_error(events)["details"]["consecutive_failures"] == 1
        _assert_compaction_prompt_before_failed(events)
    finally:
        kernel.close()
