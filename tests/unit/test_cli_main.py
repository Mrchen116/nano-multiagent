import io
import json

from nano_multiagent.cli.main import run_cli


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str] | None]] = []

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


class _FailingToolsStubClient(_StubClient):
    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        raise RuntimeError("request failed (500): {'error': 'tools unavailable'}")


class _ConnectionRefusedOnSendStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        raise ConnectionRefusedError(61, "Connection refused")


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
    payload = json.loads(output.getvalue())
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
    assert [call[0] for call in stub.calls] == [
        "create_session",
        "send_message",
        "list_session_tools",
        "compact_session",
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
    assert "Suggestion: run /new or /use <session_id>." in text
    assert "Error: missing session_id for /use." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Error: unknown command '/unknown'." in text
    assert "Suggestion: run /help to see available commands." in text


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
    assert "Suggestion: check --base-url and ensure API server is running." in text


class _ManagedServerSpy:
    def __init__(self, *, fail_on_start: Exception | None = None) -> None:
        self.fail_on_start = fail_on_start
        self.events: list[str] = []
        self.config_base_url: str | None = None

    def bind(self, base_url: str) -> "_ManagedServerSpy":
        self.config_base_url = base_url
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
        managed_server_factory=lambda config: manager.bind(config.base_url),
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
        managed_server_factory=lambda config: manager.bind(config.base_url),
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
    assert "--base-url" in payload["suggestion"]
