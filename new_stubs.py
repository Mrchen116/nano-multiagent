class _AsyncEventingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_target", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "run_status", "run_id": "run_target", "status": "queued"}
            yield {"event": "run_status", "run_id": "run_target", "status": "queued"}
            yield {"event": "assistant_message", "run_id": "run_other", "content": "ignore-me"}
            yield {"event": "tool_start", "run_id": "run_target", "name": "echo", "call_id": "call_1", "arguments": {"text": "ping"}}
            yield {"event": "tool_end", "run_id": "run_target", "name": "echo", "call_id": "call_1", "output": {"text": "echo:ping"}, "error": None}
            yield {"event": "assistant_message", "run_id": "run_target", "content": "final:echo:ping"}
        yield {"event": "run_status", "run_id": "run_target", "status": "completed", "stop_reason": "stop"}

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
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_multiline", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "tool_start", "run_id": "run_multiline", "name": "echo", "call_id": "call_ml", "arguments": {"text": "ping"}}
        yield {"event": "tool_end", "run_id": "run_multiline", "name": "echo", "call_id": "call_ml", "output": {"text": "line1\nline2"}, "error": None}
        yield {"event": "assistant_message", "run_id": "run_multiline", "content": "final:echo:ping"}
        yield {"event": "run_status", "run_id": "run_multiline", "status": "completed", "stop_reason": "stop"}

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
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_long_output", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        long_output = "HEAD-" + ("x" * 200) + "-TAIL"
        yield {"event": "tool_start", "run_id": "run_long_output", "name": "echo", "call_id": "call_long", "arguments": {"text": "ping"}}
        yield {"event": "tool_end", "run_id": "run_long_output", "name": "echo", "call_id": "call_long", "output": {"text": long_output}, "error": None}
        yield {"event": "assistant_message", "run_id": "run_long_output", "content": "final:echo:ping"}
        yield {"event": "run_status", "run_id": "run_long_output", "status": "completed", "stop_reason": "stop"}

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
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_twice", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "tool_start", "run_id": "run_twice", "name": "echo", "call_id": "call_1", "arguments": {"text": "first"}}
        yield {"event": "tool_end", "run_id": "run_twice", "name": "echo", "call_id": "call_1", "output": {"text": "echo:first"}, "error": None}
        yield {"event": "tool_start", "run_id": "run_twice", "name": "echo", "call_id": "call_2", "arguments": {"text": "second"}}
        yield {"event": "tool_end", "run_id": "run_twice", "name": "echo", "call_id": "call_2", "output": {"text": "echo:second"}, "error": None}
        yield {"event": "assistant_message", "run_id": "run_twice", "content": "final:echo:second"}
        yield {"event": "run_status", "run_id": "run_twice", "status": "completed", "stop_reason": "stop"}

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
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_same_output", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "tool_start", "run_id": "run_same_output", "name": "echo", "call_id": "call_same_1", "arguments": {"text": "same"}}
        yield {"event": "tool_end", "run_id": "run_same_output", "name": "echo", "call_id": "call_same_1", "output": {"text": "echo:same"}, "error": None}
        yield {"event": "tool_start", "run_id": "run_same_output", "name": "echo", "call_id": "call_same_2", "arguments": {"text": "same"}}
        yield {"event": "tool_end", "run_id": "run_same_output", "name": "echo", "call_id": "call_same_2", "output": {"text": "echo:same"}, "error": None}
        yield {"event": "assistant_message", "run_id": "run_same_output", "content": "final:echo:same"}
        yield {"event": "run_status", "run_id": "run_same_output", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tool_exec", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "tool_start", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "arguments": {"command": "printf out-line; printf err-line >&2", "timeout": 1}}
            yield {"event": "tool_exec_started", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "status": "started", "elapsed_ms": 0}
            yield {"event": "tool_exec_running", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "status": "running", "elapsed_ms": 120}
            yield {"event": "tool_exec_chunk", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "stream": "stdout", "chunk": "out-line", "seq": 1}
            yield {"event": "tool_exec_chunk", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "stream": "stderr", "chunk": "err-line", "seq": 2}
            yield {"event": "tool_exec_exit", "run_id": "run_tool_exec", "name": "bash", "call_id": "call_bash_1", "status": "completed", "duration_ms": 210, "exit_code": 0}
            yield {"event": "assistant_message", "run_id": "run_tool_exec", "content": "done"}
        yield {"event": "run_status", "run_id": "run_tool_exec", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_orphan", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "tool_start", "run_id": "run_orphan", "name": "bash", "call_id": "call_active", "arguments": {"command": "echo active"}}
            yield {"event": "tool_exec_started", "run_id": "run_orphan", "name": "bash", "call_id": "call_active", "status": "started", "elapsed_ms": 0}
            yield {"event": "tool_exec_exit", "run_id": "run_orphan", "name": "bash", "call_id": "call_orphan", "status": "failed", "duration_ms": 31, "exit_code": 137}
            yield {"event": "tool_exec_exit", "run_id": "run_orphan", "name": "bash", "call_id": "call_active", "status": "completed", "duration_ms": 19, "exit_code": 0}
            yield {"event": "assistant_message", "run_id": "run_orphan", "content": "final:orphan-isolated"}
        yield {"event": "run_status", "run_id": "run_orphan", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_ordered", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "assistant_message", "run_id": "run_ordered", "content": "Let's check the README file."}
            yield {"event": "tool_start", "run_id": "run_ordered", "name": "read", "call_id": "call_read_1", "arguments": {"path": "README.md"}}
            yield {"event": "tool_end", "run_id": "run_ordered", "name": "read", "call_id": "call_read_1", "output": {"path": "README.md"}, "error": None}
            yield {"event": "assistant_message", "run_id": "run_ordered", "content": "Okay, I've checked the README!"}
        yield {"event": "run_status", "run_id": "run_ordered", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_replay_tail", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "assistant_message", "run_id": "run_replay_tail", "content": "First assistant."}
            yield {"event": "tool_start", "run_id": "run_replay_tail", "name": "read", "call_id": "call_tail_1", "arguments": {"path": "README.md"}}
            yield {"event": "tool_end", "run_id": "run_replay_tail", "name": "read", "call_id": "call_tail_1", "output": {"path": "README.md"}, "error": None}
            yield {"event": "assistant_message", "run_id": "run_replay_tail", "content": "Second assistant."}
            yield {"event": "turn_end", "run_id": "run_replay_tail"}
            yield {"event": "run_status", "run_id": "run_replay_tail", "status": "completed"}
            yield {"event": "tool_start", "run_id": "run_replay_tail", "name": "read", "call_id": "call_tail_1", "arguments": {"path": "README.md"}}
            yield {"event": "tool_end", "run_id": "run_replay_tail", "name": "read", "call_id": "call_tail_1", "output": {"path": "README.md"}, "error": None}
        yield {"event": "run_status", "run_id": "run_replay_tail", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_no_event_id", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls > 2:
            return
        yield {"event": "tool_start", "run_id": "run_no_event_id", "name": "bash", "call_id": "call_no_event_id", "arguments": {"command": "echo hi"}}
        yield {"event": "tool_exec_exit", "run_id": "run_no_event_id", "name": "bash", "call_id": "call_no_event_id", "status": "completed", "duration_ms": 12, "exit_code": 0}
        yield {"event": "assistant_message", "run_id": "run_no_event_id", "content": "final:no-event-id"}
        yield {"event": "run_status", "run_id": "run_no_event_id", "status": "completed", "stop_reason": "stop"}

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

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_changed_event_id", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "tool_start", "run_id": "run_changed_event_id", "name": "bash", "call_id": "call_changed_event_id", "arguments": {"command": "echo hi"}}
            yield {"event": "tool_exec_exit", "run_id": "run_changed_event_id", "name": "bash", "call_id": "call_changed_event_id", "status": "completed", "duration_ms": 18, "exit_code": 0}
            yield {"event": "assistant_message", "run_id": "run_changed_event_id", "content": "final:changed-event-id"}
            yield {"event": "run_status", "run_id": "run_changed_event_id", "status": "completed", "stop_reason": "stop"}
        if self._stream_calls == 2:
            yield {"event": "tool_start", "run_id": "run_changed_event_id", "name": "bash", "call_id": "call_changed_event_id", "arguments": {"command": "echo hi"}}
            yield {"event": "run_status", "run_id": "run_changed_event_id", "status": "completed", "stop_reason": "stop"}

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


class _AsyncChangedEventIdWithTimestampReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_changed_event_id_ts", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "tool_start", "run_id": "run_changed_event_id_ts", "name": "bash", "call_id": "call_changed_event_id_ts", "arguments": {"command": "echo hi"}, "ts": "2026-03-04T00:00:00.100Z"}
            yield {"event": "tool_exec_started", "run_id": "run_changed_event_id_ts", "name": "bash", "call_id": "call_changed_event_id_ts", "status": "started", "elapsed_ms": 0}
            yield {"event": "run_status", "run_id": "run_changed_event_id_ts", "status": "completed", "stop_reason": "stop"}
        if self._stream_calls == 2:
            yield {"event": "tool_start", "run_id": "run_changed_event_id_ts", "name": "bash", "call_id": "call_changed_event_id_ts", "arguments": {"command": "echo hi"}, "ts": "2026-03-04T00:00:00.300Z"}
            yield {"event": "tool_exec_exit", "run_id": "run_changed_event_id_ts", "name": "bash", "call_id": "call_changed_event_id_ts", "status": "completed", "duration_ms": 19, "exit_code": 0}
            yield {"event": "assistant_message", "run_id": "run_changed_event_id_ts", "content": "final:changed-event-id-ts"}
            yield {"event": "run_status", "run_id": "run_changed_event_id_ts", "status": "completed", "stop_reason": "stop"}

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_changed_event_id_ts" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncFailedRunStubClient(_StubClient):
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_failed", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "run_status", "run_id": "run_failed", "status": "queued"}
        yield {"event": "run_status", "run_id": "run_failed", "status": "failed", "stop_reason": "timeout"}

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


class _CompletedStatusFirstStubClient(_StubClient):
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_completed_first", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        yield {"event": "run_status", "run_id": "run_completed_first", "status": "completed"}
        yield {"event": "tool_start", "run_id": "run_completed_first", "name": "echo", "call_id": "call_1", "arguments": {"text": "ping"}}
        yield {"event": "tool_end", "run_id": "run_completed_first", "name": "echo", "call_id": "call_1", "output": {"text": "echo:ping"}, "error": None}
        yield {"event": "assistant_message", "run_id": "run_completed_first", "content": "final:echo:ping"}
        yield {"event": "run_status", "run_id": "run_completed_first", "status": "completed", "stop_reason": "stop"}

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
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


class _CompletedThenTailEventsStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tail", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            yield {"event": "run_status", "run_id": "run_tail", "status": "completed"}
            yield {"event": "run_status", "run_id": "run_tail", "status": "completed", "stop_reason": "stop"}
        if self._stream_calls == 2:
            yield {"event": "tool_start", "run_id": "run_tail", "name": "echo", "call_id": "call_tail", "arguments": {"text": "tail"}}
            yield {"event": "tool_end", "run_id": "run_tail", "name": "echo", "call_id": "call_tail", "output": {"text": "echo:tail"}, "error": None}
            yield {"event": "assistant_message", "run_id": "run_tail", "content": "final:echo:tail"}
            yield {"event": "run_status", "run_id": "run_tail", "status": "completed", "stop_reason": "stop"}

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": "turn_tail",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncRetryingStatusStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._poll_count = 0

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": "run_retrying", "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        self._poll_count += 1
        if self._poll_count == 1:
            yield {"event": "run_status", "run_id": "run_retrying", "status": "running", "attempt": 1, "next_delay": 0.5, "cooldown": 0.0, "last_error": {"code": "model_error", "message": "upstream flaky #1"}}
        if self._poll_count == 2:
            yield {"event": "run_status", "run_id": "run_retrying", "status": "running", "attempt": 5, "next_delay": 1.0, "cooldown": 30.0, "last_error": {"code": "model_error", "message": "upstream flaky #5"}}
        yield {"event": "run_status", "run_id": "run_retrying", "status": "completed", "stop_reason": "completed"}

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        if self._poll_count >= 2:
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "completed",
                "created_at": "2026-03-03T00:00:00+00:00",
                "updated_at": "2026-03-03T00:00:00+00:00",
                "turn_id": "turn_retry",
                "stop_reason": "completed",
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "running",
            "created_at": "2026-03-03T00:00:00+00:00",
            "updated_at": "2026-03-03T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": None,
            "error": None,
        }


class _AsyncQueueingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._run_count = 0
        self._poll_by_run: dict[str, int] = {}

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self._run_count += 1
        run_id = f"run_queue_{self._run_count}"
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        return {"run_id": run_id, "session_id": session_id, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        self.calls.append(("stream_session", {"session_id": session_id}))
        return

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        poll_count = self._poll_by_run.get(run_id, 0) + 1
        self._poll_by_run[run_id] = poll_count
        if run_id == "run_queue_1" and poll_count < 4:
            time.sleep(0.03)
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "running",
                "created_at": "2026-03-04T00:00:00+00:00",
                "updated_at": "2026-03-04T00:00:00+00:00",
                "turn_id": None,
                "stop_reason": None,
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": f"turn_{run_id}",
            "stop_reason": "stop",
            "error": None,
        }
