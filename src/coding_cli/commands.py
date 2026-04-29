"""CLI entry orchestration over HTTP-only ServerClient interactions."""

import argparse
import asyncio
import io
import json
import os
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable, Sequence, TextIO

from coding_cli.client import ServerClient, ServerClientConfig
from coding_cli.events.background_runs import BackgroundRunEventProcessor
from coding_cli.events.event_pipeline import build_repl_view_model as _build_repl_view_model
from coding_cli.events.repl_events import _build_ordered_repl_updates
from coding_cli.events.repl_events import _event_preview_line
from coding_cli.events.repl_events import merge_text_delta as _merge_text_delta
from coding_cli.events.repl_events import print_event_preview as _print_event_preview
import coding_cli.input.repl_commands as repl_commands
import coding_cli.input.repl_input as repl_input
from coding_cli.managed_server import ManagedServerConfig, ManagedServerProcess
from coding_cli.render.context_budget import context_budget_hint_for_ratio as _context_budget_hint_for_ratio
from coding_cli.render.context_budget import context_budget_prefix as _context_budget_prefix
from coding_cli.render.context_budget import extract_context_budget_metrics as _extract_context_budget_metrics
from coding_cli.render.context_budget import print_context_budget_snapshot as _print_context_budget_snapshot
from coding_cli.render.error_presenter import error_layer_for_exception as _error_layer_for_exception
from coding_cli.render.error_presenter import suggestion_for_exception as _suggestion_for_exception
from coding_cli.render.repl_render import print_repl_turn_error as _print_repl_turn_error
from coding_cli.render.repl_render import print_repl_turn_summary as _print_repl_turn_summary
from coding_cli.render.terminal_output import emit_lines as _emit_terminal_lines
from coding_cli.render.terminal_output import write_tty_line as _write_tty_line
from coding_cli.render.turn_usage import print_turn_usage_snapshot as _print_turn_usage_snapshot
from coding_cli.session_stream import SessionStreamReader
from coding_cli.text_runner import run_text

_CLI_HELP_EPILOG = (
    "REPL quick commands: /help /new /use <session_id> /session /tools /compact /history [n] /exit\n"
    "Inline editing: ←/→ move cursor, Backspace deletes at cursor.\n"
    "History recall: ↑/↓ navigates per-session input history and restores draft.\n"
    "HTTP-only boundary: CLI orchestrates via ServerClient, never direct runtime calls.\n"
    "JSON contract: non-interactive commands print a single final JSON object on stdout.\n"
    "LLM usage: shown per turn when provider usage is available.\n"
    "Context budget: shown after each assistant reply and after /compact.\n"
    "Error layers: input / network / runtime."
)
_DEFAULT_CLI_MODE = "remote"
_REPL_DRAIN_TIMEOUT_SECONDS = 0.1
_REPL_BACKGROUND_TAIL_DRAIN_SECONDS = 0.2


def _is_tty_output(out: TextIO) -> bool:
    """Return whether the output stream is an interactive TTY."""
    isatty = getattr(out, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def _use_rich_live(out: TextIO) -> bool:
    """Return whether to use rich Live rendering for the given output stream."""
    if not _is_tty_output(out):
        return False
    if os.getenv("CODING_CLI_NO_RICH"):
        return False
    try:
        import rich.live  # noqa: F401
    except Exception:
        return False
    return True


def _emit_plain_repl_block(*, out: TextIO, text: str) -> None:
    """Emit REPL block for non-TTY outputs without terminal control sequences."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return
    if normalized.endswith("\n"):
        out.write(normalized)
    else:
        out.write(f"{normalized}\n")
    flush = getattr(out, "flush", None)
    if callable(flush):
        flush()


def _format_resume_history_block(messages: Sequence[dict[str, object]]) -> str:
    """Format resume history as one stable block so prior lines stay visible."""
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            lines.extend(f"> {line}" for line in content.splitlines() or ("",))
            continue
        if role == "assistant":
            lines.append("Assistant:")
            lines.extend(content.splitlines())
            continue
    return "\n".join(lines)


_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


@dataclass(frozen=True, slots=True)
class _ManagedLLMOverrides:
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float | None = None

    def is_empty(self) -> bool:
        """Return whether managed-mode override set is empty."""
        return (
            self.provider is None
            and self.model is None
            and self.base_url is None
            and self.api_key is None
            and self.timeout_seconds is None
        )


def build_parser() -> argparse.ArgumentParser:
    """Build command parser for REPL and single-shot CLI modes."""
    parser = argparse.ArgumentParser(
        prog="nano-multiagent-cli",
        description="Interactive Coding Agent CLI over HTTP API.",
        epilog=_CLI_HELP_EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--mode", choices=("managed", "remote"), default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--resume", default=None, help="Resume an existing session by id in REPL or --text mode.")
    parser.add_argument("--api-timeout-seconds", type=float, default=None)
    parser.add_argument("--provider", dest="llm_provider", default=None, help="Managed mode only: set local API LLM provider.")
    parser.add_argument("--model", dest="llm_model", default=None, help="Managed mode only: set local API LLM model.")
    parser.add_argument("--llm-base-url", dest="llm_base_url", default=None, help="Managed mode only: set local API LLM base URL.")
    parser.add_argument("--api-key", dest="llm_api_key", default=None, help="Managed mode only: set local API LLM API key.")
    parser.add_argument(
        "--timeout-seconds",
        dest="llm_timeout_seconds",
        type=float,
        default=None,
        help="Managed mode only: set local API LLM timeout in seconds.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Non-interactive mode: submit text and stream NDJSON events to stdout, then exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("health")

    llm_parser = subparsers.add_parser("llm-config")
    llm_subparsers = llm_parser.add_subparsers(dest="llm_config_command", required=True)
    llm_subparsers.add_parser("get")
    llm_set_parser = llm_subparsers.add_parser("set")
    llm_set_parser.add_argument("--provider", dest="llm_config_provider", default=None)
    llm_set_parser.add_argument("--model", dest="llm_config_model", default=None)
    llm_set_parser.add_argument("--base-url", dest="llm_config_base_url", default=None)
    llm_set_parser.add_argument("--api-key", dest="llm_config_api_key", default=None)
    llm_set_parser.add_argument("--clear-api-key", dest="llm_config_clear_api_key", action="store_true")
    llm_set_parser.add_argument("--timeout-seconds", dest="llm_config_timeout_seconds", type=float, default=None)

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    client_factory: Callable[[ServerClientConfig], ServerClient] | None = None,
    input_fn: Callable[[str], str] | None = None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None = None,
    managed_server_factory: Callable[[ManagedServerConfig], ManagedServerProcess] | None = None,
) -> int:
    """Run CLI command/REPL and return process exit code.

    Notes:
        Non-interactive commands always print exactly one JSON object to stdout
        so scripts can parse results without SSE/repl noise.
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out = stdout or sys.stdout
    mode = _DEFAULT_CLI_MODE

    try:
        mode = _resolve_mode(args.mode, arg_base_url=args.base_url)
        managed_llm_overrides = _resolve_managed_llm_overrides(args=args, mode=mode)
        env_config = ServerClientConfig.from_env()
        base_url = _resolve_base_url(mode=mode, arg_base_url=args.base_url, env_config=env_config)
        timeout_seconds = _resolve_timeout_seconds(mode=mode, arg_timeout_seconds=args.api_timeout_seconds, env_config=env_config)
        config = ServerClientConfig(
            base_url=base_url,
            request_id=args.request_id if args.request_id is not None else env_config.request_id,
            timeout_seconds=timeout_seconds,
        )

        factory = client_factory or (lambda cfg: ServerClient(config=cfg))
        managed_factory = managed_server_factory or (lambda cfg: ManagedServerProcess(config=cfg))
        lifecycle = _build_server_lifecycle(
            mode=mode,
            config=config,
            managed_llm_overrides=managed_llm_overrides,
            managed_server_factory=managed_factory,
        )
        with lifecycle:
            with factory(config) as client:
                if args.text is not None:
                    session_id = args.resume
                    if not session_id:
                        session_payload = client.create_session()
                        session_id = _extract_session_id(session_payload)
                    return asyncio.run(
                        run_text(
                            client=client,
                            session_id=session_id,
                            text=args.text,
                            out=out,
                        )
                    )
                if args.command is None:
                    return _run_repl(
                        args=args,
                        out=out,
                        client=client,
                        input_fn=input_fn,
                        repl_input_reader_factory=repl_input_reader_factory,
                    )
                payload = _run_single_command(args=args, client=client)
    except Exception as exc:
        layer = _error_layer_for_exception(exc)
        suggestion = _suggestion_for_exception(
            exc,
            default=(
                "check local managed API startup and retry, or switch to --mode remote."
                if mode == "managed"
                else "check --base-url and ensure remote API server is reachable."
            ),
            mode=mode,
        )
        print(
            json.dumps(
                {"error": str(exc), "layer": layer, "suggestion": suggestion},
                ensure_ascii=False,
            ),
            file=out,
        )
        return 1

    # Keep stdout machine-readable for command mode integrations.
    print(json.dumps(payload, ensure_ascii=False), file=out)
    return 0


def _run_single_command(*, args: argparse.Namespace, client: ServerClient) -> dict[str, object]:
    if args.command == "health":
        return client.health()
    if args.command == "llm-config":
        return _run_llm_config_command(args=args, client=client)
    raise ValueError(f"unsupported command: {args.command}")


def _run_llm_config_command(*, args: argparse.Namespace, client: ServerClient) -> dict[str, object]:
    if args.llm_config_command == "get":
        return client.get_llm_config()

    provider = args.llm_config_provider
    model = args.llm_config_model
    base_url = args.llm_config_base_url
    api_key = args.llm_config_api_key
    clear_api_key = bool(args.llm_config_clear_api_key)
    timeout_seconds = args.llm_config_timeout_seconds

    if api_key is not None and clear_api_key:
        raise ValueError("--api-key and --clear-api-key cannot be used together")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be > 0")
    if (
        provider is None
        and model is None
        and base_url is None
        and api_key is None
        and timeout_seconds is None
        and not clear_api_key
    ):
        raise ValueError(
            "llm-config set requires at least one field: "
            "--provider/--model/--base-url/--api-key/--clear-api-key/--timeout-seconds"
        )

    return client.set_llm_config(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        clear_api_key=clear_api_key,
    )


def _supports_sse_repl_events(client: ServerClient) -> bool:
    """Check whether client supports submit+SSE streaming required by new REPL."""
    return callable(getattr(client, "submit_message", None)) and callable(
        getattr(client, "stream_session", None)
    )


_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _grace_period_drain(
    reader: SessionStreamReader,
    *,
    out: TextIO,
    background_processor: BackgroundRunEventProcessor,
    max_wait_seconds: float = _REPL_DRAIN_TIMEOUT_SECONDS,
) -> None:
    """Briefly drain queued background completions before returning to prompt."""
    import time

    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        evt = reader.poll(timeout=min(remaining, 0.5))
        if evt is None:
            continue
        lines = background_processor.process(evt)
        _emit_terminal_lines(out, lines, is_tty=_is_tty_output(out))
        # If we just saw a terminal background run, give it a moment for
        # trailing events (assistant_message, tool_end) then exit.
        if (
            evt.get("event") == "run_status"
            and evt.get("status") in _TERMINAL_RUN_STATUSES
            and evt.get("run_id") in background_processor.seen_run_ids
        ):
            # Short tail drain for trailing events of this background run.
            tail_deadline = time.monotonic() + _REPL_BACKGROUND_TAIL_DRAIN_SECONDS
            while time.monotonic() < tail_deadline:
                tail_evt = reader.poll(timeout=0.1)
                if tail_evt is None:
                    continue
                tail_lines = background_processor.process(tail_evt)
                _emit_terminal_lines(out, tail_lines, is_tty=_is_tty_output(out))
            break


def _send_message_via_sse(
    *,
    out: TextIO,
    client: ServerClient,
    reader: SessionStreamReader,
    session_id: str,
    text: str,
    background_processor: BackgroundRunEventProcessor | None = None,
) -> dict[str, object]:
    """Submit message and drain SSE events for the run, returning a turn payload."""
    submit = client.submit_message(session_id=session_id, text=text)
    run_id = submit["run_id"]

    bg_processor = background_processor or BackgroundRunEventProcessor()

    def _on_other_event(event: dict[str, object]) -> None:
        lines = bg_processor.process(event)
        _emit_terminal_lines(out, lines, is_tty=_is_tty_output(out))

    live_rendered = False
    if _is_tty_output(out):
        from coding_cli.render.repl_tool_lines import format_tool_done, format_tool_running

        # Print events sequentially as they arrive so text and tool lines
        # appear in true execution order.  Rich Live groups ALL tool lines
        # into one persistent block at the bottom, preventing interleaving.
        _thinking_shown = [True]
        print("⠋ Thinking...", end="\r", file=out, flush=True)

        def _erase_thinking() -> None:
            if _thinking_shown[0]:
                # ANSI: carriage-return + erase to end-of-line
                print("\r\033[K", end="", file=out, flush=True)
                _thinking_shown[0] = False

        def _on_run_event_tty(event: dict[str, object]) -> None:
            _erase_thinking()
            event_name = event.get("event")
            if event_name == "assistant_message":
                content = event.get("content") or ""
                if content:
                    lines = content.split("\n")
                    # Strip trailing empty lines caused by LLM trailing newlines,
                    # but preserve internal blank lines as paragraph separators.
                    while lines and lines[-1] == "":
                        lines.pop()
                    for line in lines:
                        _write_tty_line(out, f"> {line}")
            elif event_name == "tool_start":
                name = str(event.get("name") or "?")
                # No newline: tool_end will overwrite this line.
                print(format_tool_running(name), end="\r", file=out, flush=True)
            elif event_name == "tool_end":
                name = str(event.get("name") or "?")
                duration_ms = event.get("duration_ms")
                # \r\033[K clears the tool_start line before printing completion.
                out.write(f"\r\033[K{format_tool_done(name, duration_ms)}\r\n")
                out.flush()

        events = reader.drain_run(
            run_id=run_id, timeout=0.5, terminal_timeout=120.0,
            on_other=_on_other_event, on_event=_on_run_event_tty,
        )
        _erase_thinking()
        live_rendered = True
    else:
        events: list[dict[str, object]] = []

        def _on_run_event_plain(event: dict[str, object]) -> None:
            events.append(event)
            event_name = event.get("event")
            if event_name in ("tool_start", "tool_exec_started"):
                line = _event_preview_line(event_name=event_name, data=event)
                if line:
                    print(line, file=out)

        reader.drain_run(
            run_id=run_id, timeout=0.5, terminal_timeout=120.0,
            on_other=_on_other_event, on_event=_on_run_event_plain,
        )

    assistant_text = ""
    turn_end_payload: dict[str, object] | None = None
    terminal_run_status: dict[str, object] | None = None

    for event in events:
        event_name = event.get("event")
        if event_name == "assistant_message":
            assistant_text = event.get("content") or ""
        elif event_name == "turn_end":
            turn_end_payload = event
        elif event_name == "run_status":
            status = event.get("status")
            if isinstance(status, str) and status in _TERMINAL_STATUSES:
                terminal_run_status = event

    stop_reason = None
    usage = None
    status = "unknown"
    if turn_end_payload is not None:
        stop_reason = turn_end_payload.get("stop_reason")
        usage = turn_end_payload.get("usage")
        status = "completed" if turn_end_payload.get("completed") else "failed"
    if terminal_run_status is not None:
        status = terminal_run_status.get("status") or status
        stop_reason = terminal_run_status.get("stop_reason") or stop_reason
        usage = terminal_run_status.get("usage") or usage

    if status != "completed":
        raise RuntimeError(f"run_id={run_id} run failed")

    # Build _repl_view for non-TTY summary rendering (backward-compat with old test assertions).
    legacy_events: list[tuple[str, dict[str, object]]] = []
    for event in events:
        event_name = event.get("event")
        data = dict(event)
        data.pop("event", None)
        if event_name == "assistant_message":
            event_name = "text_delta"
            data["delta"] = data.pop("content", "")
        legacy_events.append((event_name, data))

    view_model = _build_repl_view_model(
        events=legacy_events,
        preview_line_resolver=lambda name, data: _event_preview_line(event_name=name, data=data),
    )
    ordered_updates = _build_ordered_repl_updates(legacy_events)

    return {
        "session_id": session_id,
        "run_id": run_id,
        "message": {"role": "assistant", "content": assistant_text},
        "status": status,
        "completed": status == "completed",
        "stop_reason": stop_reason,
        "usage": usage,
        "_text_streamed": live_rendered,
        "_repl_view": {
            "status_updates": view_model.status_updates,
            "tool_updates": view_model.tool_updates,
            "ordered_updates": ordered_updates,
        },
    }


def _run_repl(
    *,
    args: argparse.Namespace,
    out: TextIO,
    client: ServerClient,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None = None,
) -> int:
    active_session_id = _resolve_initial_session_id(args)
    history_by_session: dict[str, list[tuple[str, str]]] = {}
    input_history_by_session: dict[str, list[str]] = {}
    sse_supported = _supports_sse_repl_events(client)
    reader: SessionStreamReader | None = None

    if _is_tty_output(out):
        def _emit_repl_block(text: str) -> None:
            repl_input.emit_persistent_text(out=out, text=text)
    else:
        def _emit_repl_block(text: str) -> None:
            _emit_plain_repl_block(out=out, text=text)

    def _print_repl_turn_summary_block(payload: dict[str, object], *, context_budget_client: object | None = None) -> None:
        buffer = io.StringIO()
        _print_repl_turn_summary(out=buffer, payload=payload, context_budget_client=context_budget_client)
        _emit_repl_block(buffer.getvalue())

    def _print_repl_turn_error_block(*, error: Exception, layer: str, suggestion: str) -> None:
        buffer = io.StringIO()
        _print_repl_turn_error(out=buffer, error=error, layer=layer, suggestion=suggestion)
        _emit_repl_block(buffer.getvalue())

    def _ensure_reader_for_session(session_id: str) -> SessionStreamReader | None:
        nonlocal reader
        if not sse_supported:
            return None
        if reader is None:
            reader = SessionStreamReader(client)
        if reader.session_id != session_id:
            reader.stop()
            reader.start(session_id=session_id)
        return reader

    if active_session_id:
        try:
            history_payload = client.get_session_messages(session_id=active_session_id, limit=100)
            messages = history_payload.get("messages", [])
            if isinstance(messages, list):
                history_block = _format_resume_history_block(messages)
                if history_block:
                    _emit_repl_block(history_block)
        except Exception as exc:
            _emit_repl_block(f"[history load failed: {exc}]")
        if sse_supported:
            _ensure_reader_for_session(active_session_id)

    background_processor = BackgroundRunEventProcessor()

    def _idle_callback() -> None:
        if reader is None:
            return
        lines: list[str] = []
        while True:
            evt = reader.poll(timeout=0.0)
            if evt is None:
                break
            lines.extend(background_processor.process(evt))

        if lines:
            _emit_repl_block("\n".join(lines))

    read_line = repl_input.build_repl_input_reader(
        out=out,
        input_fn=input_fn,
        repl_input_reader_factory=repl_input_reader_factory,
        command_suggestions=repl_commands.REPL_COMMANDS,
        on_idle=_idle_callback,
        idle_interval_seconds=0.5,
    )
    try:
        while True:
            # Drain any background events that arrived while we were idle.
            # (The idle callback also drains during prompt waits; this catches
            # any stragglers right before we start the next read.)
            if reader is not None:
                lines: list[str] = []
                while True:
                    evt = reader.poll(timeout=0.0)
                    if evt is None:
                        break
                    lines.extend(background_processor.process(evt))
                if lines:
                    _emit_repl_block("\n".join(lines))

            try:
                raw = read_line(_prompt(active_session_id), input_history_by_session.get(active_session_id or "", ()))
            except EOFError:
                _emit_repl_block("bye")
                return 0

            line = raw.strip()
            if not line:
                continue

            if repl_commands.is_repl_command_candidate(line):
                if active_session_id:
                    _append_input_history_entry(input_history_by_session, active_session_id, line)
                command_result = repl_commands.handle_repl_command(
                    line=line,
                    out=out,
                    client=client,
                    active_session_id=active_session_id,
                    history_by_session=history_by_session,
                    extract_session_id=_extract_session_id,
                    print_tools_summary=_print_tools_summary,
                    print_compact_summary=_print_compact_summary,
                    print_context_budget_snapshot=_print_context_budget_snapshot,
                    layer_for_exception=lambda exc: _error_layer_for_exception(exc, default="network"),
                    suggestion_for_exception=lambda exc, command: _suggestion_for_exception(
                        exc,
                        default=f"check server status and retry {command}.",
                    ),
                )
                active_session_id = command_result.active_session_id
                if active_session_id and sse_supported:
                    _ensure_reader_for_session(active_session_id)
                if command_result.should_exit:
                    return 0
                if command_result.handled:
                    continue

            try:
                if not active_session_id:
                    session_payload = client.create_session()
                    active_session_id = _extract_session_id(session_payload)
                    repl_commands.print_session_created(out=out, session_id=active_session_id)
                    repl_commands.print_active_session(out=out, session_id=active_session_id)
                    if sse_supported:
                        _ensure_reader_for_session(active_session_id)

                _append_input_history_entry(input_history_by_session, active_session_id, line)
                _append_history_entry(history_by_session, active_session_id, role="user", content=line)

                if not sse_supported or reader is None:
                    raise RuntimeError("client does not support SSE streaming")
                payload = _send_message_via_sse(
                    out=out,
                    client=client,
                    reader=reader,
                    session_id=active_session_id,
                    text=line,
                    background_processor=background_processor,
                )

                # Grace-period drain: background tasks that complete shortly
                # after the main run will have their events rendered here.
                _grace_period_drain(reader, out=out, background_processor=background_processor)

                response_content = _extract_message_content(payload)
                if response_content is not None:
                    _append_history_entry(
                        history_by_session,
                        active_session_id,
                        role="assistant",
                        content=response_content,
                    )
                _print_repl_turn_summary_block(payload, context_budget_client=client)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                layer = _error_layer_for_exception(exc)
                suggestion = _suggestion_for_exception(
                    exc,
                    default="run /new to start a session, then retry.",
                )
                _print_repl_turn_error_block(
                    error=RuntimeError(f"send failed: {exc}"),
                    layer=layer,
                    suggestion=suggestion,
                )
    finally:
        if reader is not None:
            reader.stop()


def _resolve_mode(raw_mode: str | None, *, arg_base_url: str | None = None) -> str:
    env_mode = os.getenv("NANO_MULTIAGENT_CLI_MODE")
    if raw_mode is None and env_mode is None:
        if arg_base_url is None:
            return "managed"
        return _DEFAULT_CLI_MODE
    value = raw_mode or env_mode or _DEFAULT_CLI_MODE
    lowered = value.strip().lower()
    if lowered not in {"managed", "remote"}:
        raise ValueError(f"unsupported --mode: {value}")
    return lowered


def _resolve_base_url(*, mode: str, arg_base_url: str | None, env_config: ServerClientConfig) -> str:
    env_base_url = os.getenv("NANO_MULTIAGENT_API_BASE_URL")
    if mode == "remote":
        value = arg_base_url or env_base_url
        if not isinstance(value, str) or not value.strip():
            raise ValueError("remote mode requires --base-url or NANO_MULTIAGENT_API_BASE_URL")
        return value.strip()
    if isinstance(arg_base_url, str) and arg_base_url.strip():
        return arg_base_url.strip()
    # Keep the no-arg front-door on the built-in managed localhost instead of
    # letting generic API env vars silently turn startup into a remote flow.
    return ServerClientConfig().base_url


def _resolve_timeout_seconds(*, mode: str, arg_timeout_seconds: float | None, env_config: ServerClientConfig) -> float:
    if arg_timeout_seconds is not None:
        if arg_timeout_seconds <= 0:
            raise ValueError("--api-timeout-seconds must be > 0")
        return arg_timeout_seconds
    timeout_from_env = os.getenv("NANO_MULTIAGENT_API_TIMEOUT_SECONDS")
    if timeout_from_env is not None:
        return env_config.timeout_seconds
    if mode == "managed":
        return 120.0
    return env_config.timeout_seconds


def _resolve_managed_llm_overrides(*, args: argparse.Namespace, mode: str) -> _ManagedLLMOverrides:
    overrides = _ManagedLLMOverrides(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        timeout_seconds=args.llm_timeout_seconds,
    )
    if mode != "managed" and not overrides.is_empty():
        raise ValueError("managed startup LLM options require --mode managed")
    if overrides.timeout_seconds is not None and overrides.timeout_seconds <= 0:
        raise ValueError("--llm-timeout-seconds must be > 0")
    return overrides


def _build_server_lifecycle(
    *,
    mode: str,
    config: ServerClientConfig,
    managed_llm_overrides: _ManagedLLMOverrides,
    managed_server_factory: Callable[[ManagedServerConfig], ManagedServerProcess],
):
    if mode == "remote":
        return nullcontext()
    managed_server = managed_server_factory(
        ManagedServerConfig(
            base_url=config.base_url,
            llm_provider=managed_llm_overrides.provider,
            llm_model=managed_llm_overrides.model,
            llm_base_url=managed_llm_overrides.base_url,
            llm_api_key=managed_llm_overrides.api_key,
            llm_timeout_seconds=managed_llm_overrides.timeout_seconds,
        )
    )

    class _Lifecycle:
        def __enter__(self):
            managed_server.start()
            return managed_server

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb
            managed_server.stop()

    return _Lifecycle()


def _append_history_entry(
    history_by_session: dict[str, list[tuple[str, str]]],
    session_id: str,
    *,
    role: str,
    content: str,
) -> None:
    entries = history_by_session.setdefault(session_id, [])
    entries.append((role, content))


def _append_input_history_entry(
    history_by_session: dict[str, list[str]],
    session_id: str,
    line: str,
) -> None:
    entries = history_by_session.setdefault(session_id, [])
    entries.append(line)


from coding_cli.render.repl_summary import _extract_message_content


def _print_tools_summary(*, out: TextIO, payload: dict[str, object]) -> None:
    session_id = payload.get("session_id")
    tools = payload.get("tools")
    resolved_session_id = session_id if isinstance(session_id, str) and session_id.strip() else "<unknown>"
    items = tools if isinstance(tools, list) else []
    print(f"Tools for session {resolved_session_id} ({len(items)}):", file=out)
    if not items:
        print("- (no tools)", file=out)
        return
    for tool in items:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        description = tool.get("description")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        resolved_description = (
            str(description) if isinstance(description, str) and description.strip() else "(no description)"
        )
        print(f"- {resolved_name}: {resolved_description}", file=out)


def _print_compact_summary(*, out: TextIO, payload: dict[str, object]) -> None:
    session_id = payload.get("session_id")
    compacted = payload.get("compacted")
    result = payload.get("result")
    resolved_session_id = session_id if isinstance(session_id, str) and session_id.strip() else "<unknown>"
    if compacted is not True or not isinstance(result, dict):
        print(f"Compaction for session {resolved_session_id}: no changes.", file=out)
        return
    print(f"Compaction for session {resolved_session_id}: compacted.", file=out)
    reason = result.get("reason")
    summary = result.get("summary")
    dropped_event_ids = result.get("dropped_event_ids")
    kept_event_ids = result.get("kept_event_ids")
    if isinstance(reason, str) and reason.strip():
        print(f"Reason: {reason}", file=out)
    if isinstance(summary, str) and summary.strip():
        print(f"Summary: {summary}", file=out)
    if isinstance(kept_event_ids, list):
        print(f"Kept events: {len(kept_event_ids)}", file=out)
    if isinstance(dropped_event_ids, list):
        print(f"Dropped events: {len(dropped_event_ids)}", file=out)


def _resolve_initial_session_id(args: argparse.Namespace) -> str | None:
    value = args.resume if args.resume is not None else ""
    return value.strip() or None


def _extract_session_id(payload: dict[str, object]) -> str:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise RuntimeError("missing session_id in response")
    return session_id


def _prompt(active_session_id: str | None) -> str:
    if active_session_id:
        return f"[{active_session_id}]> "
    return "nano> "
