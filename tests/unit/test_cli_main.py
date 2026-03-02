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
