"""Integration: CLI REPL keyboard input, inline editing, and history recall.

Tests in this file use _ScriptedReplInputReader to feed key sequences and
verify that the REPL correctly handles inline editing (arrow keys, history
up/down), slash-menu navigation, multiline paste, and invalid-command errors.
"""

import io

import httpx
import pytest

from coding_cli.input import repl_commands, repl_input
from coding_cli.main import run_cli
from agent.core.types import Message, TurnResult
from agent.core.agent.compaction.types import CompactionReason, CompactionResult
from agent.platform.http_api.app import create_app

# All tests in this file use _ScriptedReplInputReader with ASGI TestClient.
# SessionStreamReader starts a background thread for SSE, but ASGI TestClient
# event-loop isolation prevents the SSE stream from seeing events submitted
# via a different client instance. Tests hang indefinitely. (#47)
pytestmark = pytest.mark.skip(reason="REPL+ASGI hang: 跨 event-loop SSE 不可达 — tracked in #47")


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


class _RuntimeStub:
    async def run(self, session_id: str, parts, *, stream: bool = False, run_id: str | None = None, controller=None, parent_session_id=None, origin=None):
        del stream
        text = ""
        for item in parts:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                break
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cli",
            messages=(Message(message_id="msg_cli", role="assistant", content=f"cli:{text}"),),
            completed=True,
            stop_reason="stop",
        )

    async def compact(self, session_id: str) -> CompactionResult:
        return CompactionResult(
            reason=CompactionReason.MANUAL,
            entry_id="entry_cli_compact",
            first_kept_event_id="evt_cli_kept",
            summary="cli compacted",
            dropped_event_ids=("evt_cli_drop",),
            kept_event_ids=("evt_cli_kept",),
        )


def test_cli_repl_inline_editing_keys_submit_edited_text() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:helXlo" in text


def test_cli_repl_history_recall_allows_second_submit_after_editing() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["p", "i", "n", "g", "\n"],
            ["\x1b[A", "\x1b[D", "\x1b[D", "X", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:ping" in text
    assert "Queued message #1" in text
    assert "cli:piXng" not in text


def test_cli_repl_full_chain_edit_history_and_compact_budget_state() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

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
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:helXlo" in text
    assert "cli:helXlo!" in text
    assert "History for session" in text
    assert "user: helXlo!" in text
    assert "Compaction for session" in text
    assert "Context budget (after /compact):" in text


def test_cli_repl_up_recalls_previous_command_line() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["/", "h", "e", "l", "p", "\n"],
            ["\x1b[A", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    assert output.getvalue().count("Commands: /help /new /use <session_id>") == 2


def test_cli_repl_slash_menu_selects_command_and_executes_it() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "\x1b[B", "\n", "\n"],
            ["/", "s", "e", "s", "s", "i", "o", "n", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )
    output = io.StringIO()
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: unknown command '/'" not in text
    assert "Active session: sess_" in text
    assert '{"session_id":' not in text
    assert "Commands ↓ " not in text


def test_cli_repl_session_transitions_render_active_copy_without_json() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["hello http", "/new", "/use sess_manual", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Started new session sess_") == 2
    assert text.count("Active session: sess_") >= 2
    assert "Switched to session sess_manual." in text
    assert "Active session: sess_manual." in text
    assert '{"session_id":' not in text
    assert '"session_id":' not in text


def test_cli_repl_multiline_paste_submits_single_async_message() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        [
            ["/", "\x1b[B", "\n", "\n"],
            ["f", "i", "r", "s", "t", "\nsecond\n"],
            ["/", "\x1b[A", "\n", "\n"],
        ]
    )
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "cli:first\nsecond" in text
    assert "Queued message #1" not in text
    assert text.count("run=") == 1


def test_cli_repl_rejects_invalid_command_arguments() -> None:
    app = create_app(runtime=_RuntimeStub())
    transport = httpx.ASGITransport(app=app)

    def client_factory(config):
        from coding_cli.client import ServerClient

        return ServerClient(config=config, transport=transport)

    output = io.StringIO()
    inputs = iter(["/new extra", "/tools now", "/exit"])
    exit_code = run_cli(
        ["--base-url", "http://testserver"],
        stdout=output,
        client_factory=client_factory,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: command /new does not accept arguments." in text
    assert "Layer: input" in text
    assert "Suggestion: try /new." in text
    assert "Usage: /new" in text
    assert "Error: command /tools does not accept arguments." in text
    assert "Suggestion: try /tools." in text
    assert "Usage: /tools" in text
