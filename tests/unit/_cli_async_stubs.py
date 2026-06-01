"""Async stub clients for CLI event rendering tests.

这些 stub 模拟各种 SSE event 流序列，供 test_cli_repl_async.py 使用。
不以 test_ 开头，pytest 不会直接采集，但可以被同目录测试文件通过
`from tests.unit._cli_async_stubs import ...` 导入。
"""

import io


class _TTYStringIO(io.StringIO):
    """StringIO that reports isatty()=True for tty-branch coverage."""

    def isatty(self) -> bool:
        return True


def _simulate_terminal_rows(text: str) -> list[str]:
    """Replay ANSI cursor-up + carriage-return sequences to produce final terminal rows."""
    rows: list[str] = [""]
    cursor = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\r":
            cursor = 0
            i += 1
        elif ch == "\n":
            cursor = 0
            rows.append("")
            i += 1
        elif ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            j = i + 2
            while j < len(text) and (text[j].isdigit() or text[j] == ";"):
                j += 1
            if j < len(text):
                cmd = text[j]
                param_str = text[i + 2 : j]
                n = int(param_str) if param_str.isdigit() else 1
                if cmd == "A":
                    rows_to_move = min(n, len(rows) - 1)
                    current_row_index = len(rows) - 1
                    target_row_index = current_row_index - rows_to_move
                    while len(rows) - 1 > target_row_index:
                        rows.pop()
                    cursor = 0
                i = j + 1
            else:
                i += 1
        else:
            row = rows[-1]
            if cursor < len(row):
                rows[-1] = row[:cursor] + ch + row[cursor + 1 :]
            else:
                rows[-1] = row + " " * (cursor - len(row)) + ch
            cursor += 1
            i += 1
    return rows


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        return {"healthy": True}

    def create_session(
        self, *, title: str | None = None, **kwargs: object
    ) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        self._last_text = text
        return {
            "run_id": "run-1",
            "anchor_sequence": 1,
            "injected": False,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        text = getattr(self, "_last_text", "hello repl")
        yield {
            "event": "assistant_message",
            "run_id": "run-1",
            "content": f"echo:{text}",
        }
        yield {
            "event": "run_status",
            "run_id": "run-1",
            "status": "completed",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }


class _AsyncEventingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_target", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "run_status", "run_id": "run_target", "status": "queued"}
            yield {"event": "run_status", "run_id": "run_target", "status": "queued"}
            yield {
                "event": "assistant_message",
                "run_id": "run_other",
                "content": "ignore-me",
            }
            yield {
                "event": "tool_start",
                "run_id": "run_target",
                "name": "echo",
                "call_id": "call_1",
                "arguments": {"text": "ping"},
            }
            yield {
                "event": "tool_end",
                "run_id": "run_target",
                "name": "echo",
                "call_id": "call_1",
                "output": {"text": "echo:ping"},
                "error": None,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_target",
                "content": "final:echo:ping",
            }
        yield {
            "event": "run_status",
            "run_id": "run_target",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        if self._stream_calls >= 1:
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "completed",
                "created_at": "2026-03-02T00:00:00+00:00",
                "updated_at": "2026-03-02T00:00:00+00:00",
                "turn_id": "turn_async",
                "stop_reason": "stop",
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "running",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": None,
            "error": None,
        }


class _AsyncMultilineToolOutputStubClient(_StubClient):
    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_multiline", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {
            "event": "tool_start",
            "run_id": "run_multiline",
            "name": "echo",
            "call_id": "call_ml",
            "arguments": {"text": "ping"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_multiline",
            "name": "echo",
            "call_id": "call_ml",
            "output": {"text": "line1\nline2"},
            "error": None,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run_multiline",
            "content": "final:echo:ping",
        }
        yield {
            "event": "run_status",
            "run_id": "run_multiline",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_ml",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncUsageEventingStubClient(_AsyncEventingStubClient):
    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        async for event in super().stream_session(
            session_id=session_id, last_event_id=last_event_id
        ):
            if (
                event.get("event") == "run_status"
                and event.get("status") == "completed"
            ):
                event = dict(event)
                event["usage"] = {
                    "prompt_tokens": 320,
                    "completion_tokens": 41,
                    "total_tokens": 361,
                }
            yield event

    def get_run(self, *, run_id: str) -> dict[str, object]:
        payload = super().get_run(run_id=run_id)
        if payload["status"] == "completed":
            payload["usage"] = {
                "prompt_tokens": 320,
                "completion_tokens": 41,
                "total_tokens": 361,
            }
        return payload


class _AsyncLongToolOutputStubClient(_StubClient):
    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {
            "run_id": "run_long_output",
            "session_id": session_id,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        long_output = "HEAD-" + ("x" * 200) + "-TAIL"
        yield {
            "event": "tool_start",
            "run_id": "run_long_output",
            "name": "echo",
            "call_id": "call_long",
            "arguments": {"text": "ping"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_long_output",
            "name": "echo",
            "call_id": "call_long",
            "output": {"text": long_output},
            "error": None,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run_long_output",
            "content": "final:echo:ping",
        }
        yield {
            "event": "run_status",
            "run_id": "run_long_output",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_long_output",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncSameToolTwiceStubClient(_StubClient):
    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_twice", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {
            "event": "tool_start",
            "run_id": "run_twice",
            "name": "echo",
            "call_id": "call_1",
            "arguments": {"text": "first"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_twice",
            "name": "echo",
            "call_id": "call_1",
            "output": {"text": "echo:first"},
            "error": None,
        }
        yield {
            "event": "tool_start",
            "run_id": "run_twice",
            "name": "echo",
            "call_id": "call_2",
            "arguments": {"text": "second"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_twice",
            "name": "echo",
            "call_id": "call_2",
            "output": {"text": "echo:second"},
            "error": None,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run_twice",
            "content": "final:echo:second",
        }
        yield {
            "event": "run_status",
            "run_id": "run_twice",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_twice",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncSameToolSameOutputStubClient(_StubClient):
    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {
            "run_id": "run_same_output",
            "session_id": session_id,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {
            "event": "tool_start",
            "run_id": "run_same_output",
            "name": "echo",
            "call_id": "call_same_1",
            "arguments": {"text": "same"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_same_output",
            "name": "echo",
            "call_id": "call_same_1",
            "output": {"text": "echo:same"},
            "error": None,
        }
        yield {
            "event": "tool_start",
            "run_id": "run_same_output",
            "name": "echo",
            "call_id": "call_same_2",
            "arguments": {"text": "same"},
        }
        yield {
            "event": "tool_end",
            "run_id": "run_same_output",
            "name": "echo",
            "call_id": "call_same_2",
            "output": {"text": "echo:same"},
            "error": None,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run_same_output",
            "content": "final:echo:same",
        }
        yield {
            "event": "run_status",
            "run_id": "run_same_output",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_same_output",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncToolExecStreamingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tool_exec", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {
                "event": "tool_start",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "arguments": {
                    "command": "printf out-line; printf err-line >&2",
                    "timeout": 1,
                },
            }
            yield {
                "event": "tool_exec_started",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "status": "started",
                "elapsed_ms": 0,
            }
            yield {
                "event": "tool_exec_running",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "status": "running",
                "elapsed_ms": 120,
            }
            yield {
                "event": "tool_exec_chunk",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "stream": "stdout",
                "chunk": "out-line",
                "seq": 1,
            }
            yield {
                "event": "tool_exec_chunk",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "stream": "stderr",
                "chunk": "err-line",
                "seq": 2,
            }
            yield {
                "event": "tool_exec_exit",
                "run_id": "run_tool_exec",
                "name": "bash",
                "call_id": "call_bash_1",
                "status": "completed",
                "duration_ms": 210,
                "exit_code": 0,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_tool_exec",
                "content": "done",
            }
        yield {
            "event": "run_status",
            "run_id": "run_tool_exec",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_tool_exec",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncOrphanExecExitStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_orphan", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {
                "event": "tool_start",
                "run_id": "run_orphan",
                "name": "bash",
                "call_id": "call_active",
                "arguments": {"command": "echo active"},
            }
            yield {
                "event": "tool_exec_started",
                "run_id": "run_orphan",
                "name": "bash",
                "call_id": "call_active",
                "status": "started",
                "elapsed_ms": 0,
            }
            yield {
                "event": "tool_exec_exit",
                "run_id": "run_orphan",
                "name": "bash",
                "call_id": "call_orphan",
                "status": "failed",
                "duration_ms": 31,
                "exit_code": 137,
            }
            yield {
                "event": "tool_exec_exit",
                "run_id": "run_orphan",
                "name": "bash",
                "call_id": "call_active",
                "status": "completed",
                "duration_ms": 19,
                "exit_code": 0,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_orphan",
                "content": "final:orphan-isolated",
            }
        yield {
            "event": "run_status",
            "run_id": "run_orphan",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_orphan" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncAssistantToolAssistantStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_ordered", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {
                "event": "assistant_message",
                "run_id": "run_ordered",
                "content": "Let's check the README file.",
            }
            yield {
                "event": "tool_start",
                "run_id": "run_ordered",
                "name": "read",
                "call_id": "call_read_1",
                "arguments": {"path": "README.md"},
            }
            yield {
                "event": "tool_end",
                "run_id": "run_ordered",
                "name": "read",
                "call_id": "call_read_1",
                "output": {"path": "README.md"},
                "error": None,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_ordered",
                "content": "Okay, I've checked the README!",
            }
        yield {
            "event": "run_status",
            "run_id": "run_ordered",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "turn_id": "turn_ordered",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncReplayAfterTurnEndStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {
            "run_id": "run_replay_tail",
            "session_id": session_id,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {
                "event": "assistant_message",
                "run_id": "run_replay_tail",
                "content": "First assistant.",
            }
            yield {
                "event": "tool_start",
                "run_id": "run_replay_tail",
                "name": "read",
                "call_id": "call_tail_1",
                "arguments": {"path": "README.md"},
            }
            yield {
                "event": "tool_end",
                "run_id": "run_replay_tail",
                "name": "read",
                "call_id": "call_tail_1",
                "output": {"path": "README.md"},
                "error": None,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_replay_tail",
                "content": "Second assistant.",
            }
            yield {"event": "turn_end", "run_id": "run_replay_tail"}
            yield {
                "event": "run_status",
                "run_id": "run_replay_tail",
                "status": "completed",
            }
            yield {
                "event": "tool_start",
                "run_id": "run_replay_tail",
                "name": "read",
                "call_id": "call_tail_1",
                "arguments": {"path": "README.md"},
            }
            yield {
                "event": "tool_end",
                "run_id": "run_replay_tail",
                "name": "read",
                "call_id": "call_tail_1",
                "output": {"path": "README.md"},
                "error": None,
            }
        yield {
            "event": "run_status",
            "run_id": "run_replay_tail",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "turn_id": "turn_replay_tail",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncNoEventIdReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {
            "run_id": "run_no_event_id",
            "session_id": session_id,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls > 2:
            return
        yield {
            "event": "tool_start",
            "run_id": "run_no_event_id",
            "name": "bash",
            "call_id": "call_no_event_id",
            "arguments": {"command": "echo hi"},
        }
        yield {
            "event": "tool_exec_exit",
            "run_id": "run_no_event_id",
            "name": "bash",
            "call_id": "call_no_event_id",
            "status": "completed",
            "duration_ms": 12,
            "exit_code": 0,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run_no_event_id",
            "content": "final:no-event-id",
        }
        yield {
            "event": "run_status",
            "run_id": "run_no_event_id",
            "status": "completed",
            "stop_reason": "stop",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_no_event_id" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncChangedEventIdReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {
            "run_id": "run_changed_event_id",
            "session_id": session_id,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {
                "event": "tool_start",
                "run_id": "run_changed_event_id",
                "name": "bash",
                "call_id": "call_changed_event_id",
                "arguments": {"command": "echo hi"},
            }
            yield {
                "event": "tool_exec_exit",
                "run_id": "run_changed_event_id",
                "name": "bash",
                "call_id": "call_changed_event_id",
                "status": "completed",
                "duration_ms": 18,
                "exit_code": 0,
            }
            yield {
                "event": "assistant_message",
                "run_id": "run_changed_event_id",
                "content": "final:changed-event-id",
            }
            yield {
                "event": "run_status",
                "run_id": "run_changed_event_id",
                "status": "completed",
                "stop_reason": "stop",
            }
        if self._stream_calls == 2:
            yield {
                "event": "tool_start",
                "run_id": "run_changed_event_id",
                "name": "bash",
                "call_id": "call_changed_event_id",
                "arguments": {"command": "echo hi"},
            }
            yield {
                "event": "run_status",
                "run_id": "run_changed_event_id",
                "status": "completed",
                "stop_reason": "stop",
            }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_changed_event_id" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncFailedRunStubClient(_StubClient):
    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_failed", "session_id": session_id, "status": "queued"}

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "run_status", "run_id": "run_failed", "status": "queued"}
        yield {
            "event": "run_status",
            "run_id": "run_failed",
            "status": "failed",
            "stop_reason": "timeout",
        }

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "failed",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": "timeout",
            "error": {
                "code": "run_timeout",
                "message": "timed out waiting for upstream; root_cause=connect ETIMEDOUT",
            },
        }


class _ResumeHistoryStubClient(_StubClient):
    def get_session_messages(
        self, *, session_id: str, limit: int = 20
    ) -> dict[str, object]:
        self.calls.append(
            ("get_session_messages", {"session_id": session_id, "limit": limit})
        )
        return {
            "session_id": session_id,
            "messages": [
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
                {"role": "tool", "content": "tool output should stay hidden"},
                {"role": "assistant", "content": "second line 1\nsecond line 2"},
            ],
        }
