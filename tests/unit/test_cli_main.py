import io
import json

from nano_multiagent.cli import commands as cli_commands
from nano_multiagent.cli import repl_input
from nano_multiagent.cli import repl_commands
from nano_multiagent.cli.main import run_cli


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

    def create_session(self, *, title: str | None = None) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        return {"session_id": session_id, "message": {"content": f"echo:{text}"}}

    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "tools": [{"name": "read", "description": "Read", "input_schema": {}}],
        }

    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {"session_id": session_id, "compacted": False, "result": None}

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }

    def get_llm_config(self) -> dict[str, object]:
        self.calls.append(("get_llm_config", None))
        return {
            "provider": "openai_compat",
            "model": "codexOAuth:gpt-5.2-codex",
            "base_url": "http://127.0.0.1:4000",
            "api_key_configured": False,
            "timeout_seconds": 30.0,
        }

    def set_llm_config(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "set_llm_config",
                {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                    "api_key": api_key,
                    "timeout_seconds": timeout_seconds,
                    "clear_api_key": clear_api_key,
                },
            )
        )
        resolved_api_key = None if clear_api_key else api_key
        return {
            "provider": provider or "openai_compat",
            "model": model or "codexOAuth:gpt-5.2-codex",
            "base_url": base_url or "http://127.0.0.1:4000",
            "api_key_configured": bool(resolved_api_key),
            "timeout_seconds": timeout_seconds or 30.0,
        }


class _CompactedStubClient(_StubClient):
    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "compacted": True,
            "result": {
                "summary": "context compacted",
                "kept_event_ids": ["evt_keep_1", "evt_keep_2"],
                "dropped_event_ids": ["evt_drop_1"],
            },
        }


class _ThresholdBudgetStubClient(_StubClient):
    def __init__(self, *, used_tokens: int, max_tokens: int) -> None:
        super().__init__()
        self._used_tokens = used_tokens
        self._max_tokens = max_tokens

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        usage_ratio = float(self._used_tokens) / float(self._max_tokens)
        return {
            "session_id": session_id,
            "used_tokens": self._used_tokens,
            "max_tokens": self._max_tokens,
            "remaining_tokens": max(self._max_tokens - self._used_tokens, 0),
            "usage_ratio": usage_ratio,
        }


class _FailingBudgetStubClient(_StubClient):
    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        raise RuntimeError("request failed (503): {'error': 'budget unavailable'}")


class _FailingToolsStubClient(_StubClient):
    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        raise RuntimeError("request failed (500): {'error': 'tools unavailable'}")


class _ConnectionRefusedOnSendStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        raise ConnectionRefusedError(61, "Connection refused")


class _TimeoutOnSendStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        raise TimeoutError("timed out")


class _ConnectionRefusedOnHealthStubClient(_StubClient):
    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        raise ConnectionRefusedError(61, "Connection refused")


class _AsyncEventingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_target", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_dup",
                    "event": "run_status",
                    "data": {"run_id": "run_target", "status": "queued"},
                },
                {
                    "event_id": "evt_dup",
                    "event": "run_status",
                    "data": {"run_id": "run_target", "status": "queued"},
                },
                {
                    "event_id": "evt_other",
                    "event": "text_delta",
                    "data": {"run_id": "run_other", "delta": "ignore-me"},
                },
                {
                    "event_id": "evt_tool_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_target",
                        "name": "echo",
                        "call_id": "call_1",
                        "arguments": {"text": "ping"},
                    },
                },
                {
                    "event_id": "evt_tool_end",
                    "event": "tool_end",
                    "data": {
                        "run_id": "run_target",
                        "name": "echo",
                        "call_id": "call_1",
                        "output": {"text": "echo:ping"},
                        "error": None,
                    },
                },
                {
                    "event_id": "evt_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_target", "delta": "final:echo:ping"},
                },
            ]
        return []

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


class _AsyncFailedRunStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_failed", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_fail_queued",
                "event": "run_status",
                "data": {"run_id": "run_failed", "status": "queued"},
            }
        ]

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
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_completed_first", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_completed",
                "event": "run_status",
                "data": {"run_id": "run_completed_first", "status": "completed"},
            },
            {
                "event_id": "evt_tool_start",
                "event": "tool_start",
                "data": {
                    "run_id": "run_completed_first",
                    "name": "echo",
                    "call_id": "call_1",
                    "arguments": {"text": "ping"},
                },
            },
            {
                "event_id": "evt_tool_end",
                "event": "tool_end",
                "data": {
                    "run_id": "run_completed_first",
                    "name": "echo",
                    "call_id": "call_1",
                    "output": {"text": "echo:ping"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_text",
                "event": "text_delta",
                "data": {"run_id": "run_completed_first", "delta": "final:echo:ping"},
            },
        ]

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

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tail", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_tail_completed",
                    "event": "run_status",
                    "data": {"run_id": "run_tail", "status": "completed"},
                }
            ]
        if self._stream_calls == 2:
            return [
                {
                    "event_id": "evt_tail_tool_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_tail",
                        "name": "echo",
                        "call_id": "call_tail",
                        "arguments": {"text": "tail"},
                    },
                },
                {
                    "event_id": "evt_tail_tool_end",
                    "event": "tool_end",
                    "data": {
                        "run_id": "run_tail",
                        "name": "echo",
                        "call_id": "call_tail",
                        "output": {"text": "echo:tail"},
                        "error": None,
                    },
                },
                {
                    "event_id": "evt_tail_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_tail", "delta": "final:echo:tail"},
                },
            ]
        return []

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


def _iter_keys(keys: list[str]):
    iterator = iter(keys)

    def _reader() -> str | None:
        try:
            return next(iterator)
        except StopIteration:
            return None

    return _reader


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        keys = next(self._line_iterator)
        key_iterator = iter(keys)

        def _read_key() -> str | None:
            try:
                return next(key_iterator)
            except StopIteration:
                return None

        return repl_input.read_interactive_line(
            prompt=prompt,
            history=tuple(history),
            key_reader=_read_key,
            out=self.render,
            command_suggestions=repl_commands.REPL_COMMANDS,
        )


def test_repl_input_engine_supports_inline_insert_at_cursor() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "helXlo"


def test_repl_input_engine_supports_left_right_with_backspace_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["a", "b", "c", "\x1b[D", "\x7f", "\x1b[C", "!", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "ac!"


def test_repl_input_engine_arrow_up_recalls_and_allows_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "secoXnd"


def test_repl_input_engine_history_navigation_moves_up_and_down() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[A", "\x1b[B", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "second"


def test_repl_input_engine_slash_menu_down_enter_fills_selected_command() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[B", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/new"


def test_repl_input_engine_slash_menu_up_wraps_without_history_recall() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[A", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/exit"


def test_run_cli_repl_up_recalls_previous_command_line() -> None:
    stub = _StubClient()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["/", "h", "e", "l", "p", "\n"],
            ["\x1b[A", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    assert output.getvalue().count("Commands: /help /new /use <session_id>") == 2


def test_cli_help_mentions_repl_editing_budget_and_error_layers() -> None:
    help_text = cli_commands.build_parser().format_help()

    assert "REPL quick commands" in help_text
    assert "/compact /history [n] /exit" in help_text
    assert "Inline editing" in help_text
    assert "History recall" in help_text
    assert "HTTP-only boundary" in help_text
    assert "single final JSON object on stdout" in help_text
    assert "Error layers: input / network / runtime" in help_text


def test_run_cli_health_outputs_json_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert stub.calls == [("health", None)]


def test_run_cli_send_message_uses_session_id_from_env(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_SESSION_ID", "sess_env")
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "send-message",
            "--text",
            "ping",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    raw = output.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
    assert payload["session_id"] == "sess_env"
    assert payload["message"]["content"] == "echo:ping"


def test_run_cli_repl_supports_required_commands() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/help", "/new", "hello repl", "/session", "/tools", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    lines = output.getvalue()
    assert "/help /new /use <session_id> /session /tools /compact" in lines
    assert "/history [n]" in lines
    assert "/exit" in lines
    assert "session_id" in lines
    assert "hello repl" in lines
    assert "Tools for session sess_cli (1):" in lines
    assert "- read: Read" in lines
    assert "Compaction for session sess_cli: no changes." in lines
    assert "Context budget: 64/200 (32.0%)" in lines
    assert [call[0] for call in stub.calls] == [
        "create_session",
        "send_message",
        "get_context_budget",
        "list_session_tools",
        "compact_session",
        "get_context_budget",
    ]


def test_run_cli_repl_use_switches_active_session() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/use sess_manual", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    assert ("send_message", {"session_id": "sess_manual", "text": "ping"}) in stub.calls


def test_run_cli_repl_history_shows_recent_messages() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/history 2", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session sess_cli (last 2/4):" in text
    assert "user: second" in text
    assert "assistant: echo:second" in text
    assert "assistant: echo:first" not in text


def test_run_cli_repl_command_errors_include_actionable_suggestions() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/tools", "/use", "/unknown", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: no active session." in text
    assert "Layer: input" in text
    assert "Suggestion: run /new or /use <session_id>." in text
    assert "Error: missing session_id for /use." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Error: unknown command '/unknown'." in text
    assert "Suggestion: run /help to see available commands." in text


def test_run_cli_repl_absolute_path_input_is_not_treated_as_command() -> None:
    stub = _StubClient()
    output = io.StringIO()
    path_line = "/Users/czj/Repos/nano-multiagent/Snipaste_2026-03-03_12-54-14.png这个呢"
    inputs = iter(["/new", path_line, "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert f"echo:{path_line}" in text
    assert "unknown command" not in text
    assert ("send_message", {"session_id": "sess_cli", "text": path_line}) in stub.calls


def test_run_cli_repl_ignores_blank_input_and_exits_on_eof() -> None:
    stub = _StubClient()
    output = io.StringIO()
    calls = iter(["   "])

    def _input(_: str) -> str:
        try:
            return next(calls)
        except StopIteration as exc:
            raise EOFError() from exc

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=_input,
    )

    assert exit_code == 0
    assert output.getvalue().strip() == "bye"
    assert stub.calls == []


def test_run_cli_repl_rejects_invalid_command_arguments() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new extra", "/session now", "/use a b", "/history 0", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: command /new does not accept arguments." in text
    assert "Layer: input" in text
    assert "Suggestion: try /new." in text
    assert "Usage: /new" in text
    assert "Error: command /session does not accept arguments." in text
    assert "Suggestion: try /session." in text
    assert "Usage: /session" in text
    assert "Error: /use expects exactly one session_id." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Usage: /use <session_id>" in text
    assert "Error: invalid n for /history." in text
    assert "Suggestion: try /history 10." in text
    assert "Usage: /history [n]" in text
    assert ("create_session", {"title": ""}) not in stub.calls


def test_run_cli_repl_compact_summary_displays_key_fields() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text
    assert "Summary: context compacted" in text
    assert "Kept events: 2" in text
    assert "Dropped events: 1" in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_compact_prints_post_compact_budget_state_line() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_edit_history_budget_compact_chain_regression() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["\x1b[A", "\x1b[C", "!", "\n"],
            ["/", "c", "o", "m", "p", "a", "c", "t", "\n"],
            ["/", "h", "i", "s", "t", "o", "r", "y", " ", "4", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:helXlo" in text
    assert "echo:helXlo!" in text
    assert "History for session sess_cli" in text
    assert "user: helXlo!" in text
    assert "Compaction for session sess_cli: compacted." in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_context_budget_shows_threshold_hint() -> None:
    stub = _ThresholdBudgetStubClient(used_tokens=174, max_tokens=200)
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "Context budget: 174/200 (87.0%)" in text
    assert "Budget hint: usage >= 85%, consider /compact soon." in text


def test_run_cli_repl_context_budget_fetch_failure_is_fail_open() -> None:
    stub = _FailingBudgetStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "Context budget: unavailable" in text


def test_run_cli_repl_request_failures_include_suggestions() -> None:
    stub = _FailingToolsStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/tools", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: failed to run /tools." in text
    assert "Layer: network" in text
    assert "Suggestion: check server status/token and retry /tools." in text


def test_run_cli_repl_connection_refused_shows_base_url_suggestion() -> None:
    stub = _ConnectionRefusedOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: send failed: [Errno 61] Connection refused" in text
    assert "Layer: network" in text
    assert "Suggestion: check --base-url and ensure API server is running." in text


def test_run_cli_repl_timeout_shows_timeout_tuning_suggestion() -> None:
    stub = _TimeoutOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    text = output.getvalue().lower()
    assert "send failed: timed out" in text
    assert "layer: network" in text
    assert "nano_multiagent_api_timeout_seconds" in text


def test_run_cli_repl_uses_async_events_with_run_filter_and_dedup() -> None:
    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("status=queued") == 1
    assert "[tool echo] start" in text
    assert "[tool echo] output=echo:ping" in text
    assert "[text] final:echo:ping" in text
    assert "ignore-me" not in text
    assert ("send_message_async", {"session_id": "sess_cli", "text": "ping"}) in stub.calls


def test_run_cli_repl_failed_run_error_includes_run_id_for_diagnosis() -> None:
    stub = _AsyncFailedRunStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: send failed: run_id=run_failed" in text
    assert "Layer: runtime" in text
    assert "NANO_MULTIAGENT_API_TIMEOUT_SECONDS" in text


def test_run_cli_repl_delays_terminal_run_status_until_after_tool_tail_events() -> None:
    stub = _CompletedStatusFirstStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    completed_idx = text.find("status=completed")
    tool_output_idx = text.find("[tool echo] output=echo:ping")
    assert completed_idx != -1
    assert tool_output_idx != -1
    assert completed_idx > tool_output_idx


def test_run_cli_repl_drains_tail_events_after_terminal_run_status() -> None:
    stub = _CompletedThenTailEventsStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "[tool echo] start" in text
    assert "[tool echo] output=echo:tail" in text
    assert "[text] final:echo:tail" in text


class _ManagedServerSpy:
    def __init__(self, *, fail_on_start: Exception | None = None) -> None:
        self.fail_on_start = fail_on_start
        self.events: list[str] = []
        self.config_base_url: str | None = None
        self.config_token: str | None = None
        self.llm_provider: str | None = None
        self.llm_model: str | None = None
        self.llm_base_url: str | None = None
        self.llm_api_key: str | None = None
        self.llm_timeout_seconds: float | None = None

    def bind(self, config: object) -> "_ManagedServerSpy":
        self.config_base_url = getattr(config, "base_url", None)
        self.config_token = getattr(config, "token", None)
        self.llm_provider = getattr(config, "llm_provider", None)
        self.llm_model = getattr(config, "llm_model", None)
        self.llm_base_url = getattr(config, "llm_base_url", None)
        self.llm_api_key = getattr(config, "llm_api_key", None)
        self.llm_timeout_seconds = getattr(config, "llm_timeout_seconds", None)
        return self

    def start(self) -> None:
        self.events.append("start")
        if self.fail_on_start is not None:
            raise self.fail_on_start

    def stop(self) -> None:
        self.events.append("stop")


def test_run_cli_managed_mode_starts_and_stops_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8111",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert manager.config_base_url == "http://127.0.0.1:8111"
    assert manager.events == ["start", "stop"]


def test_run_cli_remote_mode_does_not_start_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8112",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not start")),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}


def test_run_cli_managed_mode_start_failure_surfaces_actionable_suggestion() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy(fail_on_start=RuntimeError("port 8000 already in use"))

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "port 8000 already in use" in payload["error"]
    assert "remote" in payload["suggestion"].lower()


def test_run_cli_remote_mode_requires_base_url_with_actionable_error() -> None:
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not build client")),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "remote mode requires --base-url" in payload["error"]
    assert payload["layer"] == "input"
    assert "--base-url" in payload["suggestion"]


def test_run_cli_remote_mode_connection_failure_suggestion_mentions_remote_api() -> None:
    stub = _ConnectionRefusedOnHealthStubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8222",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "connection refused" in payload["error"].lower()
    assert payload["layer"] == "network"
    assert "remote api" in payload["suggestion"].lower()


def test_run_cli_managed_mode_uses_higher_default_timeout_when_not_configured() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8113", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 120.0


def test_run_cli_respects_explicit_api_timeout_seconds() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8114",
            "--token",
            "test-token",
            "--api-timeout-seconds",
            "45",
            "health",
        ],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 45.0


def test_run_cli_llm_config_get_outputs_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "--token", "test-token", "llm-config", "get"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "openai_compat"
    assert stub.calls == [("get_llm_config", None)]


def test_run_cli_llm_config_set_applies_requested_fields() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "llm-config",
            "set",
            "--provider",
            "anthropic",
            "--model",
            "claude-3-5-sonnet-20241022",
            "--base-url",
            "http://127.0.0.1:4100",
            "--api-key",
            "sk-cli",
            "--timeout-seconds",
            "55",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "anthropic"
    assert stub.calls == [
        (
            "set_llm_config",
            {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "base_url": "http://127.0.0.1:4100",
                "api_key": "sk-cli",
                "timeout_seconds": 55.0,
                "clear_api_key": False,
            },
        )
    ]


def test_run_cli_llm_config_set_requires_at_least_one_field() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "--token", "test-token", "llm-config", "set"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "at least one" in payload["error"].lower()
    assert payload["layer"] == "input"
    assert "llm-config set" in payload["suggestion"]


def test_run_cli_llm_config_set_rejects_conflicting_api_key_flags() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "llm-config",
            "set",
            "--api-key",
            "sk-cli",
            "--clear-api-key",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "cannot be used together" in payload["error"].lower()
    assert "choose either" in payload["suggestion"].lower()


def test_run_cli_managed_mode_forwards_llm_startup_options_to_managed_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8115",
            "--token",
            "test-token",
            "--llm-provider",
            "anthropic",
            "--llm-model",
            "claude-3-5-sonnet-20241022",
            "--llm-base-url",
            "http://127.0.0.1:4100",
            "--llm-api-key",
            "sk-managed",
            "--llm-timeout-seconds",
            "75",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert manager.config_base_url == "http://127.0.0.1:8115"
    assert manager.config_token == "test-token"
    assert manager.llm_provider == "anthropic"
    assert manager.llm_model == "claude-3-5-sonnet-20241022"
    assert manager.llm_base_url == "http://127.0.0.1:4100"
    assert manager.llm_api_key == "sk-managed"
    assert manager.llm_timeout_seconds == 75.0
