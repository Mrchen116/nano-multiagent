"""Kernel stubs for CLI REPL unit tests (refactor-387 M2).

这些 stub 模拟 agent.sdk.Kernel 接口，供 M2 后的 CLI 测试使用。
不以 test_ 开头，pytest 不直接采集，但可被同目录测试文件导入。

接口规则（与 agent.sdk.Kernel 对齐）：
- create_session(...) → 返回有 .session_id 属性的对象（async）
- submit(...) → 返回有 .run_id 属性的对象（sync, non-blocking）
- stream(session_id) → AsyncIterator[dict]（持久流）
- compact(session_id, ...) → dict (async)
- list_session_tools(session_id, ...) → dict/object (sync)
- interrupt(session_id) → str | None (sync)
- close() → None
- get_llm_config() → config-like object (sync)
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, AsyncIterator


class _TTYStringIO(io.StringIO):
    """StringIO that reports isatty()=True for tty-branch coverage."""

    def isatty(self) -> bool:
        return True


@dataclass
class _StubSession:
    session_id: str


@dataclass
class _StubRunRecord:
    run_id: str


@dataclass
class _StubLLMConfig:
    provider: str = "anthropic"
    model: str = "kimiCoding:K2.6"
    base_url: str = "http://127.0.0.1:4000"
    api_key: str | None = None
    timeout_seconds: float = 30.0


class _AsyncIterEvents:
    """Async iterator over a static list of events."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = iter(events)

    def __aiter__(self) -> "_AsyncIterEvents":
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration


class _BaseKernelStub:
    """Base Kernel stub — override stream() in subclasses for specific event sequences."""

    def __init__(self, *, session_id: str = "sess_cli") -> None:
        self._session_id = session_id
        self._llm_config = _StubLLMConfig()
        self.calls: list[tuple[str, Any]] = []
        self._run_id_counter = 0
        self._last_text: str = "hello repl"
        self._compact_result: dict = {"compacted": False, "result": None}
        self._tools_result: dict = {
            "session_id": "sess_cli",
            "tools": [{"name": "read", "description": "Read", "input_schema": {}}],
        }
        self._context_budget: dict = {
            "session_id": "sess_cli",
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: Any = None,
        skills: list[str] | None = None,
        **kwargs: Any,
    ) -> _StubSession:
        self.calls.append(("create_session", {"title": title, "skills": skills}))
        return _StubSession(session_id=self._session_id)

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: Any = None,
        workspace_root: Any = None,
        trace_id: str | None = None,
        model: str | None = None,
    ) -> _StubRunRecord:
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(
            ("submit", {"session_id": session_id, "text": text, "model": model})
        )
        self._run_id_counter += 1
        return _StubRunRecord(run_id=f"run-{self._run_id_counter}")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        """Return async iterator of events for session. Override in subclasses."""
        run_id = f"run-{self._run_id_counter}"
        text = self._last_text
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": run_id,
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": run_id,
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                },
            ]
        )

    async def compact(
        self, session_id: str, *, workspace_root: Any = None
    ) -> dict[str, Any]:
        self.calls.append(("compact", {"session_id": session_id}))
        return self._compact_result

    def list_session_tools(
        self, session_id: str, *, workspace_root: Any = None
    ) -> dict[str, Any]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return self._tools_result

    async def fork_session(
        self, session_id: str, *, workspace_root: Any = None
    ) -> _StubSession:
        self.calls.append(("fork_session", {"session_id": session_id}))
        return _StubSession(session_id=f"{session_id}-fork")

    def interrupt(self, session_id: str) -> str | None:
        self.calls.append(("interrupt", {"session_id": session_id}))
        return f"run-{self._run_id_counter}"

    def cancel(self, run_id: str) -> _StubRunRecord | None:
        self.calls.append(("cancel", {"run_id": run_id}))
        return None

    def get_run(self, run_id: str) -> _StubRunRecord | None:
        return None

    def close(self) -> None:
        self.calls.append(("close", None))

    async def aclose(self) -> None:
        self.calls.append(("aclose", None))

    def get_llm_config(self) -> _StubLLMConfig:
        self.calls.append(("get_llm_config", None))
        return self._llm_config


def _make_kernel_factory(stub: _BaseKernelStub):
    """Build a kernel_factory callable from a stub."""

    def factory(**_kwargs: Any) -> _BaseKernelStub:
        return stub

    return factory


# ---------------------------------------------------------------------------
# Specialized stubs for async event rendering tests
# ---------------------------------------------------------------------------


class _KernelWithEvents(_BaseKernelStub):
    """Kernel stub with configurable event sequences per stream() call."""

    def __init__(
        self,
        *,
        session_id: str = "sess_cli",
        stream_events_by_call: list[list[dict[str, Any]]] | None = None,
        default_events: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(session_id=session_id)
        self._stream_events_by_call = stream_events_by_call or []
        self._default_events = default_events
        self._stream_call_count = 0

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        call_index = self._stream_call_count
        self._stream_call_count += 1
        if call_index < len(self._stream_events_by_call):
            events = self._stream_events_by_call[call_index]
        elif self._default_events is not None:
            events = self._default_events
        else:
            run_id = f"run-{self._run_id_counter}"
            text = self._last_text
            events = [
                {
                    "event": "assistant_message",
                    "run_id": run_id,
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": run_id,
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        return _AsyncIterEvents(events)


class _AsyncEventingKernelStub(_BaseKernelStub):
    """Stub simulating tool events + assistant reply sequence."""

    def __init__(self) -> None:
        super().__init__()
        self._stream_call_count = 0

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_target")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        # Real Kernel.stream() replays the full event set on every subscription
        # (history replay + live), independent of which subscriber called first.
        # bugfix-426-M2 made REPL input non-blocking, so the per-run drive is no
        # longer guaranteed to be the *first* stream() caller — returning the
        # complete sequence on every call mirrors the real Kernel and removes the
        # brittle "first caller gets full events" coupling.
        self._stream_call_count += 1
        events = [
            {"event": "run_status", "run_id": "run_target", "status": "queued"},
            {"event": "run_status", "run_id": "run_target", "status": "queued"},
            {
                "event": "assistant_message",
                "run_id": "run_other",
                "content": "ignore-me",
            },
            {
                "event": "tool_start",
                "run_id": "run_target",
                "name": "echo",
                "call_id": "call_1",
                "arguments": {"text": "ping"},
            },
            {
                "event": "tool_end",
                "run_id": "run_target",
                "name": "echo",
                "call_id": "call_1",
                "output": {"text": "echo:ping"},
                "error": None,
            },
            {
                "event": "assistant_message",
                "run_id": "run_target",
                "content": "final:echo:ping",
            },
            {
                "event": "run_status",
                "run_id": "run_target",
                "status": "completed",
                "stop_reason": "stop",
            },
        ]
        return _AsyncIterEvents(events)


class _AsyncMultilineToolKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_multiline")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_multiline",
                    "name": "echo",
                    "call_id": "call_ml",
                    "arguments": {"text": "ping"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_multiline",
                    "name": "echo",
                    "call_id": "call_ml",
                    "output": {"text": "line1\nline2"},
                    "error": None,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_multiline",
                    "content": "final:echo:ping",
                },
                {
                    "event": "run_status",
                    "run_id": "run_multiline",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncLongToolOutputKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_long_output")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        long_output = "HEAD-" + ("x" * 200) + "-TAIL"
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_long_output",
                    "name": "echo",
                    "call_id": "call_long",
                    "arguments": {"text": "ping"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_long_output",
                    "name": "echo",
                    "call_id": "call_long",
                    "output": {"text": long_output},
                    "error": None,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_long_output",
                    "content": "final:echo:ping",
                },
                {
                    "event": "run_status",
                    "run_id": "run_long_output",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncSameToolTwiceKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_twice")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_1",
                    "arguments": {"text": "first"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_1",
                    "output": {"text": "echo:first"},
                    "error": None,
                },
                {
                    "event": "tool_start",
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_2",
                    "arguments": {"text": "second"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_2",
                    "output": {"text": "echo:second"},
                    "error": None,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_twice",
                    "content": "final:echo:second",
                },
                {
                    "event": "run_status",
                    "run_id": "run_twice",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncSameToolSameOutputKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_same_output")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_1",
                    "arguments": {"text": "same"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_1",
                    "output": {"text": "echo:same"},
                    "error": None,
                },
                {
                    "event": "tool_start",
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_2",
                    "arguments": {"text": "same"},
                },
                {
                    "event": "tool_end",
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_2",
                    "output": {"text": "echo:same"},
                    "error": None,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_same_output",
                    "content": "final:echo:same",
                },
                {
                    "event": "run_status",
                    "run_id": "run_same_output",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncToolExecStreamingKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_tool_exec")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "arguments": {
                        "command": "printf out-line; printf err-line >&2",
                        "timeout": 1,
                    },
                },
                {
                    "event": "tool_exec_started",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "status": "started",
                    "elapsed_ms": 0,
                },
                {
                    "event": "tool_exec_running",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "status": "running",
                    "elapsed_ms": 120,
                },
                {
                    "event": "tool_exec_chunk",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "stream": "stdout",
                    "chunk": "out-line",
                    "seq": 1,
                },
                {
                    "event": "tool_exec_chunk",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "stream": "stderr",
                    "chunk": "err-line",
                    "seq": 2,
                },
                {
                    "event": "tool_exec_exit",
                    "run_id": "run_tool_exec",
                    "name": "bash",
                    "call_id": "call_bash_1",
                    "status": "completed",
                    "duration_ms": 210,
                    "exit_code": 0,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_tool_exec",
                    "content": "done",
                },
                {
                    "event": "run_status",
                    "run_id": "run_tool_exec",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncOrphanExecExitKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_orphan")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_orphan",
                    "name": "bash",
                    "call_id": "call_active",
                    "arguments": {"command": "echo active"},
                },
                {
                    "event": "tool_exec_started",
                    "run_id": "run_orphan",
                    "name": "bash",
                    "call_id": "call_active",
                    "status": "started",
                    "elapsed_ms": 0,
                },
                {
                    "event": "tool_exec_exit",
                    "run_id": "run_orphan",
                    "name": "bash",
                    "call_id": "call_orphan",
                    "status": "failed",
                    "duration_ms": 31,
                    "exit_code": 137,
                },
                {
                    "event": "tool_exec_exit",
                    "run_id": "run_orphan",
                    "name": "bash",
                    "call_id": "call_active",
                    "status": "completed",
                    "duration_ms": 19,
                    "exit_code": 0,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_orphan",
                    "content": "final:orphan-isolated",
                },
                {
                    "event": "run_status",
                    "run_id": "run_orphan",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _AsyncFailedRunKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_failed")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents(
            [
                {"event": "run_status", "run_id": "run_failed", "status": "queued"},
                {
                    "event": "run_status",
                    "run_id": "run_failed",
                    "status": "failed",
                    "stop_reason": "timeout",
                },
            ]
        )


class _AsyncNoEventIdReplayKernelStub(_BaseKernelStub):
    def __init__(self) -> None:
        super().__init__()
        self._stream_call_count = 0

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_no_event_id")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        self._stream_call_count += 1
        if self._stream_call_count <= 2:
            return _AsyncIterEvents(
                [
                    {
                        "event": "tool_start",
                        "run_id": "run_no_event_id",
                        "name": "bash",
                        "call_id": "call_no_event_id",
                        "arguments": {"command": "echo hi"},
                    },
                    {
                        "event": "tool_exec_exit",
                        "run_id": "run_no_event_id",
                        "name": "bash",
                        "call_id": "call_no_event_id",
                        "status": "completed",
                        "duration_ms": 12,
                        "exit_code": 0,
                    },
                    {
                        "event": "assistant_message",
                        "run_id": "run_no_event_id",
                        "content": "final:no-event-id",
                    },
                    {
                        "event": "run_status",
                        "run_id": "run_no_event_id",
                        "status": "completed",
                        "stop_reason": "stop",
                    },
                ]
            )
        return _AsyncIterEvents([])


class _AsyncChangedEventIdReplayKernelStub(_BaseKernelStub):
    def __init__(self) -> None:
        super().__init__()
        self._stream_call_count = 0

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run_changed_event_id")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        # Real Kernel.stream() replays the full event set on every subscription
        # regardless of call order; a single per-run subscription sees tool_start
        # once, so within-stream dedupe keeps the rendered start line unique.
        # bugfix-426-M2: non-blocking input dropped the "first caller gets full
        # events" ordering, so every call returns the complete sequence.
        self._stream_call_count += 1
        return _AsyncIterEvents(
            [
                {
                    "event": "tool_start",
                    "run_id": "run_changed_event_id",
                    "name": "bash",
                    "call_id": "call_changed_event_id",
                    "arguments": {"command": "echo hi"},
                },
                {
                    "event": "tool_exec_exit",
                    "run_id": "run_changed_event_id",
                    "name": "bash",
                    "call_id": "call_changed_event_id",
                    "status": "completed",
                    "duration_ms": 18,
                    "exit_code": 0,
                },
                {
                    "event": "assistant_message",
                    "run_id": "run_changed_event_id",
                    "content": "final:changed-event-id",
                },
                {
                    "event": "run_status",
                    "run_id": "run_changed_event_id",
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )


class _UsageKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run-1")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        text = self._last_text
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 35,
                        "total_tokens": 155,
                    },
                },
            ]
        )


class _CompactedKernelStub(_BaseKernelStub):
    def __init__(self) -> None:
        super().__init__()
        self._compact_result = {
            "compacted": True,
            "result": {
                "summary": "context compacted",
                "kept_event_ids": ["evt_keep_1", "evt_keep_2"],
                "dropped_event_ids": ["evt_drop_1"],
            },
        }

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run-1")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        text = self._last_text
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                },
            ]
        )


class _ThresholdBudgetKernelStub(_BaseKernelStub):
    def __init__(self, *, used_tokens: int, max_tokens: int) -> None:
        super().__init__()
        self._context_budget = {
            "session_id": "sess_cli",
            "used_tokens": used_tokens,
            "max_tokens": max_tokens,
            "remaining_tokens": max(max_tokens - used_tokens, 0),
            "usage_ratio": float(used_tokens) / float(max_tokens),
        }

    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self._last_text = text
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        return _StubRunRecord(run_id="run-1")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        text = self._last_text
        return _AsyncIterEvents(
            [
                {
                    "event": "assistant_message",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "content": f"echo:{text}",
                },
                {
                    "event": "run_status",
                    "run_id": "run-1",
                    "session_id": session_id,
                    "status": "completed",
                    "stop_reason": "stop",
                },
            ]
        )

    def get_context_budget(self, session_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._context_budget


class _FailingToolsKernelStub(_BaseKernelStub):
    def list_session_tools(self, session_id: str, **kwargs: Any) -> dict:
        raise RuntimeError("tools unavailable")


class _ConnectionRefusedKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        raise ConnectionRefusedError(61, "Connection refused")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents([])


class _TimeoutKernelStub(_BaseKernelStub):
    def submit(self, *, session_id, parts, **kwargs):
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.calls.append(("submit", {"session_id": session_id, "text": text}))
        raise TimeoutError("timed out")

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        return _AsyncIterEvents([])
