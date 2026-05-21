"""REPL 命令行为测试。

覆盖 /help、/new、/use、/session、/tools、/compact、/history、/exit
等 REPL 命令的行为，以及 context budget 阈值提示、错误建议、
连接失败提示、超时提示等 REPL 会话层行为。
"""

import io
import json

from coding_cli import commands as cli_commands
from coding_cli.input import repl_input
from coding_cli.main import run_cli


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


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

    def create_session(self, *, title: str | None = None, **kwargs: object) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        self._last_text = text
        return {"run_id": "run-1", "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        text = getattr(self, "_last_text", "hello repl")
        yield {"event": "assistant_message", "run_id": "run-1", "content": f"echo:{text}"}
        yield {"event": "run_status", "run_id": "run-1", "status": "completed", "stop_reason": "stop", "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return {"session_id": session_id, "tools": [{"name": "read", "description": "Read", "input_schema": {}}]}

    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {"session_id": session_id, "compacted": False, "result": None}

    def get_session_messages(self, *, session_id: str, limit: int = 20) -> dict[str, object]:
        self.calls.append(("get_session_messages", {"session_id": session_id, "limit": limit}))
        return {"session_id": session_id, "messages": []}

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {"session_id": session_id, "used_tokens": 64, "max_tokens": 200, "remaining_tokens": 136, "usage_ratio": 0.32}

    def get_llm_config(self) -> dict[str, object]:
        self.calls.append(("get_llm_config", None))
        return {"provider": "openai_compat", "model": "codex_oauth:gpt-5.5", "base_url": "http://127.0.0.1:4000", "api_key_configured": False, "timeout_seconds": 30.0}

    def set_llm_config(self, *, provider=None, model=None, base_url=None, api_key=None, timeout_seconds=None, clear_api_key=False) -> dict[str, object]:
        self.calls.append(("set_llm_config", {"provider": provider, "model": model, "base_url": base_url, "api_key": api_key, "timeout_seconds": timeout_seconds, "clear_api_key": clear_api_key}))
        return {"provider": provider or "openai_compat", "model": model or "codex_oauth:gpt-5.5", "base_url": base_url or "http://127.0.0.1:4000", "api_key_configured": bool(api_key), "timeout_seconds": timeout_seconds or 30.0}


class _UsageStubClient(_StubClient):
    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        text = getattr(self, "_last_text", "hello")
        yield {"event": "assistant_message", "run_id": "run-1", "content": f"echo:{text}"}
        yield {"event": "run_status", "run_id": "run-1", "status": "completed", "stop_reason": "stop", "usage": {"prompt_tokens": 120, "completion_tokens": 35, "total_tokens": 155}}


class _StopReasonOnlyStubClient(_StubClient):
    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        del last_event_id
        text = getattr(self, "_last_text", "hello")
        yield {"event": "assistant_message", "run_id": "run-1", "content": f"echo:{text}"}
        yield {"event": "run_status", "run_id": "run-1", "status": "completed", "stop_reason": "stop"}


class _CompactedStubClient(_StubClient):
    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {"session_id": session_id, "compacted": True, "result": {"summary": "context compacted", "kept_event_ids": ["evt_keep_1", "evt_keep_2"], "dropped_event_ids": ["evt_drop_1"]}}


class _ThresholdBudgetStubClient(_StubClient):
    def __init__(self, *, used_tokens: int, max_tokens: int) -> None:
        super().__init__()
        self._used_tokens = used_tokens
        self._max_tokens = max_tokens

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        usage_ratio = float(self._used_tokens) / float(self._max_tokens)
        return {"session_id": session_id, "used_tokens": self._used_tokens, "max_tokens": self._max_tokens, "remaining_tokens": max(self._max_tokens - self._used_tokens, 0), "usage_ratio": usage_ratio}


class _FailingBudgetStubClient(_StubClient):
    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        raise RuntimeError("request failed (503): {'error': 'budget unavailable'}")


class _FailingToolsStubClient(_StubClient):
    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        raise RuntimeError("request failed (500): {'error': 'tools unavailable'}")


class _ResumeHistoryStubClient(_StubClient):
    def get_session_messages(self, *, session_id: str, limit: int = 20) -> dict[str, object]:
        self.calls.append(("get_session_messages", {"session_id": session_id, "limit": limit}))
        return {"session_id": session_id, "messages": [{"role": "user", "content": "first question"}, {"role": "assistant", "content": "first answer"}, {"role": "tool", "content": "tool output should stay hidden"}, {"role": "assistant", "content": "second line 1\nsecond line 2"}]}


class _ConnectionRefusedOnSendStubClient(_StubClient):
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        raise ConnectionRefusedError(61, "Connection refused")


class _TimeoutOnSendStubClient(_StubClient):
    def submit_message(self, *, session_id: str, text: str, priority: str = "next", message_id: str | None = None) -> dict[str, object]:
        self.calls.append(("submit_message", {"session_id": session_id, "text": text}))
        raise TimeoutError("timed out")


class _ManagedServerSpy:
    """Managed-server test double that records start/stop lifecycle events."""

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


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        from coding_cli.input import repl_commands
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_help_mentions_repl_editing_budget_and_error_layers() -> None:
    help_text = cli_commands.build_parser().format_help()

    assert "REPL quick commands" in help_text
    assert "/compact /history [n] /exit" in help_text
    assert "Inline editing" in help_text
    assert "History recall" in help_text
    assert "HTTP-only boundary" in help_text
    assert "single final JSON object on stdout" in help_text
    assert "LLM usage: shown per turn" in help_text
    assert "Error layers: input / network / runtime" in help_text


def test_run_cli_health_outputs_json_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "health"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert stub.calls == [("health", None)]


def test_run_cli_repl_supports_required_commands() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/help", "/new", "hello repl", "/session", "/tools", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    lines = output.getvalue()
    assert "/help /new /use <session_id> /session /tools /compact" in lines
    assert "/history [n]" in lines
    assert "/exit" in lines
    assert "Started new session sess_cli." in lines
    assert "Active session: sess_cli." in lines
    assert '{"session_id":' not in lines
    assert "hello repl" in lines
    assert "Tools for session sess_cli (1):" in lines
    assert "- read: Read" in lines
    assert "Compaction for session sess_cli: no changes." in lines
    assert "Context budget: 64/200 (32.0%)" in lines
    assert [call[0] for call in stub.calls] == [
        "create_session",
        "submit_message",
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
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    assert "Switched to session sess_manual." in output.getvalue()
    assert ("submit_message", {"session_id": "sess_manual", "text": "ping"}) in stub.calls


def test_run_cli_repl_session_transitions_render_active_copy_without_json() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["hello auto", "/new", "/use sess_manual", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Started new session sess_cli.") == 2
    assert text.count("Active session: sess_cli.") >= 2
    assert "Switched to session sess_manual." in text
    assert "Active session: sess_manual." in text
    assert '{"session_id":' not in text
    assert '"session_id":' not in text


def test_run_cli_repl_history_shows_recent_messages() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/history 2", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert f"echo:{path_line}" in text
    assert "unknown command" not in text
    assert ("submit_message", {"session_id": "sess_cli", "text": path_line}) in stub.calls


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
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=_input,
    )

    assert exit_code == 0
    # feat-333-M3/R2: REPL now prints an auto mode startup banner before the
    # session loop, so the output contains the banner followed by "bye" on EOF.
    text = output.getvalue()
    assert "Auto mode" in text or "auto mode" in text, (
        f"Expected auto mode banner in REPL output, got: {text!r}"
    )
    assert "bye" in text
    assert stub.calls == []


def test_run_cli_repl_rejects_invalid_command_arguments() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new extra", "/session now", "/use a b", "/history 0", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
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
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "Context budget: unavailable" in text


def test_run_cli_repl_prints_turn_llm_usage_when_available() -> None:
    stub = _UsageStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "State: completed | stop=stop" in text
    assert "Usage: prompt=120, completion=35, total=155" in text
    assert "[status]" not in text
    assert "[usage]" not in text


def test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason() -> None:
    stub = _StopReasonOnlyStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed | stop=stop" in text


def test_run_cli_repl_request_failures_include_suggestions() -> None:
    stub = _FailingToolsStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/tools", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: failed to run /tools." in text
    assert "Layer: network" in text
    assert "Suggestion: check server status and retry /tools." in text


def test_run_cli_repl_connection_refused_shows_base_url_suggestion() -> None:
    stub = _ConnectionRefusedOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "send failed: [Errno 61] Connection refused" in text
    assert "layer=network" in text
    assert "suggestion=check --base-url and ensure API server is running." in text


def test_run_cli_repl_timeout_shows_timeout_tuning_suggestion() -> None:
    stub = _TimeoutOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8000"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    text = output.getvalue().lower()
    assert "assistant: (empty)" in text
    assert "send failed: timed out" in text
    assert "layer=network" in text
    assert "agent_api_timeout_seconds" in text
