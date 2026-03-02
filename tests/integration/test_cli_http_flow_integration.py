import io
import json

import httpx

from nano_multiagent.agent.compaction.types import CompactionReason, CompactionResult
from nano_multiagent.cli.main import run_cli
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = False):
        del stream
        text = ""
        for item in parts:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                break
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cli",
            messages=(
                Message(
                    message_id="msg_cli",
                    role="assistant",
                    content=f"cli:{text}",
                ),
            ),
            completed=True,
            stop_reason="stop",
        )

    def compact(self, session_id: str) -> CompactionResult:
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_cli_compact",
            first_kept_event_id="evt_cli_kept",
            summary="cli compacted",
            dropped_event_ids=("evt_cli_drop",),
            kept_event_ids=("evt_cli_kept",),
        )


def test_cli_runs_http_flow_against_asgi_app() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    create_out = io.StringIO()
    create_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "create-session",
            "--title",
            "cli-session",
        ],
        stdout=create_out,
        client_factory=client_factory,
    )

    assert create_code == 0
    created = json.loads(create_out.getvalue())
    session_id = created["session_id"]

    send_out = io.StringIO()
    send_code = run_cli(
        [
            "--base-url",
            "http://testserver",
            "--token",
            "test-token",
            "send-message",
            "--session-id",
            session_id,
            "--text",
            "ping",
        ],
        stdout=send_out,
        client_factory=client_factory,
    )

    assert send_code == 0
    payload = json.loads(send_out.getvalue())
    assert payload["session_id"] == session_id
    assert payload["message"]["content"] == "cli:ping"


def test_cli_repl_flow_supports_tools_and_compact_commands() -> None:
    app = create_app(runtime=_RuntimeStub(), auth_token="test-token")
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from nano_multiagent.cli.http_client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new", "ping", "/tools", "/compact", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver", "--token", "test-token"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:ping" in text
    assert "\"tools\"" in text
    assert "\"compacted\"" in text
