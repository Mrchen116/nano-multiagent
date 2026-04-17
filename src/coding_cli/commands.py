"""CLI entry orchestration over HTTP-only ServerClient interactions."""

import argparse
import io
import json
import os
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable, Sequence, TextIO

from coding_cli.client import ServerClient, ServerClientConfig
from coding_cli.events.repl_events import consume_async_run_events as _consume_async_run_events
from coding_cli.events.repl_events import merge_text_delta as _merge_text_delta
from coding_cli.events.repl_events import print_event_preview as _print_event_preview
from coding_cli.events.repl_events import send_message_with_async_events as _send_message_with_async_events
from coding_cli.events.repl_events import supports_async_repl_events as _supports_async_repl_events
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
from coding_cli.render.turn_usage import print_turn_usage_snapshot as _print_turn_usage_snapshot
from coding_cli.runtime.repl_runtime import QueuedReplMessage, ReplRunQueue

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
_REPL_DRAIN_TIMEOUT_SECONDS = 5.0


def _is_tty_output(out: TextIO) -> bool:
    """Return whether the output stream is an interactive TTY."""
    isatty = getattr(out, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


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


def _wait_for_inflight_messages(
    *,
    run_queue: ReplRunQueue,
    emit_block: Callable[[str], None],
    before_action: str,
    timeout_seconds: float,
) -> bool:
    """Wait for REPL in-flight messages before executing a barrier action."""
    pending_before = run_queue.backlog_size()
    if pending_before <= 0:
        return True
    emit_block(f"Waiting for {pending_before} in-flight message(s) before {before_action}.")
    drained = run_queue.wait_for_drain(timeout_seconds=timeout_seconds)
    if drained:
        return True
    remaining = run_queue.backlog_size()
    if remaining <= 0:
        return True
    emit_block(
        f"Timed out waiting for in-flight messages before {before_action}; "
        f"{remaining} still in-flight message(s)."
    )
    return False


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

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("health")

    create_parser = subparsers.add_parser("create-session")
    create_parser.add_argument("--title", default=None)

    send_parser = subparsers.add_parser("send-message")
    send_parser.add_argument("--session-id", default=None)
    send_parser.add_argument("--text", required=True)

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
                if args.command is None:
                    return _run_repl(
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
    if args.command == "create-session":
        return client.create_session(title=args.title, skills=[])
    if args.command == "llm-config":
        return _run_llm_config_command(args=args, client=client)
    session_id = args.session_id or os.getenv("NANO_MULTIAGENT_SESSION_ID")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session id is required: use --session-id or NANO_MULTIAGENT_SESSION_ID")
    return client.send_message(session_id=session_id, text=args.text)


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


def _run_repl(
    *,
    out: TextIO,
    client: ServerClient,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None = None,
) -> int:
    active_session_id = _resolve_initial_session_id()
    history_by_session: dict[str, list[tuple[str, str]]] = {}
    input_history_by_session: dict[str, list[str]] = {}
    async_repl_enabled = _supports_async_repl_events(client)

    if _is_tty_output(out):
        def _emit_external_repl_block(text: str) -> None:
            repl_input.emit_external_text(out=out, text=text)
    else:
        def _emit_external_repl_block(text: str) -> None:
            _emit_plain_repl_block(out=out, text=text)

    def _print_repl_turn_summary_block(payload: dict[str, object], *, context_budget_client: object | None = None) -> None:
        buffer = io.StringIO()
        _print_repl_turn_summary(out=buffer, payload=payload, context_budget_client=context_budget_client)
        _emit_external_repl_block(buffer.getvalue())

    def _print_repl_turn_error_block(*, error: Exception, layer: str, suggestion: str) -> None:
        buffer = io.StringIO()
        _print_repl_turn_error(out=buffer, error=error, layer=layer, suggestion=suggestion)
        _emit_external_repl_block(buffer.getvalue())

    def _process_queued_message(item: QueuedReplMessage) -> None:
        try:
            payload = _send_message_from_repl(
                out=out,
                client=client,
                session_id=item.session_id,
                text=item.text,
                preview_writer=_emit_external_repl_block,
            )
            response_content = _extract_message_content(payload)
            if response_content is not None:
                _append_history_entry(
                    history_by_session,
                    item.session_id,
                    role="assistant",
                    content=response_content,
                )
            _print_repl_turn_summary_block(payload, context_budget_client=client)
        except Exception as exc:
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

    run_queue = ReplRunQueue(process_message=_process_queued_message) if async_repl_enabled else None

    read_line = repl_input.build_repl_input_reader(
        out=out,
        input_fn=input_fn,
        repl_input_reader_factory=repl_input_reader_factory,
        command_suggestions=repl_commands.REPL_COMMANDS,
    )
    try:
        while True:
            try:
                raw = read_line(_prompt(active_session_id), input_history_by_session.get(active_session_id or "", ()))
            except EOFError:
                if run_queue is not None:
                    _wait_for_inflight_messages(
                        run_queue=run_queue,
                        emit_block=_emit_external_repl_block,
                        before_action="exit",
                        timeout_seconds=_REPL_DRAIN_TIMEOUT_SECONDS,
                    )
                _emit_external_repl_block("bye")
                return 0

            line = raw.strip()
            if not line:
                continue

            if repl_commands.is_repl_command_candidate(line):
                command_name = line.split(maxsplit=1)[0]
                if run_queue is not None and command_name != "/exit":
                    drained = _wait_for_inflight_messages(
                        run_queue=run_queue,
                        emit_block=_emit_external_repl_block,
                        before_action=command_name,
                        timeout_seconds=_REPL_DRAIN_TIMEOUT_SECONDS,
                    )
                    if not drained:
                        _emit_external_repl_block(f"Skipping {command_name} for now.")
                        continue
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
                if command_result.should_exit:
                    if run_queue is not None:
                        has_active_work = getattr(run_queue, "has_active_work", None)
                        queue_has_active_work = bool(has_active_work()) if callable(has_active_work) else False
                        backlog_size = run_queue.backlog_size()
                        queue_has_pending_backlog = backlog_size > (1 if queue_has_active_work else 0)
                        if not queue_has_active_work and queue_has_pending_backlog:
                            queue_has_active_work = True
                        close_kwargs = {
                            "wait_for_drain": queue_has_active_work,
                            "drain_timeout_seconds": _REPL_DRAIN_TIMEOUT_SECONDS,
                        }
                        if queue_has_pending_backlog:
                            close_kwargs["discard_pending"] = True
                        run_queue.close(**close_kwargs)
                        run_queue = None
                    return 0
                if command_result.handled:
                    continue

            try:
                if not active_session_id:
                    session_payload = client.create_session()
                    active_session_id = _extract_session_id(session_payload)
                    repl_commands.print_session_created(out=out, session_id=active_session_id)
                    repl_commands.print_active_session(out=out, session_id=active_session_id)

                _append_input_history_entry(input_history_by_session, active_session_id, line)
                _append_history_entry(history_by_session, active_session_id, role="user", content=line)

                if run_queue is None:
                    payload = _send_message_from_repl(
                        out=out,
                        client=client,
                        session_id=active_session_id,
                        text=line,
                    )
                    response_content = _extract_message_content(payload)
                    if response_content is not None:
                        _append_history_entry(
                            history_by_session,
                            active_session_id,
                            role="assistant",
                            content=response_content,
                        )
                    _print_repl_turn_summary(
                        out=out,
                        payload=payload,
                        context_budget_client=client,
                    )
                    continue

                # If a run is actively executing, inject into its pending queue via priority='next'.
                has_active = run_queue.has_active_work()
                import sys
                sys.stderr.write(f"[DEBUG] has_active_work={has_active} line={line!r}\n")
                if has_active:
                    try:
                        injected_resp = client.send_message_async(
                            session_id=active_session_id,
                            text=line,
                            priority="next",
                        )
                        sys.stderr.write(f"[DEBUG] injection resp={injected_resp!r}\n")
                        if injected_resp.get("status") == "injected":
                            _emit_external_repl_block(f"Injected into active run for session {active_session_id}.")
                            continue
                    except Exception as exc:
                        sys.stderr.write(f"[DEBUG] injection exception={exc!r}\n")
                        # Injection failed (e.g. race: run finished before request reached server).
                        # Fall through to normal enqueue.
                        pass

                backlog_before = run_queue.enqueue(session_id=active_session_id, text=line)
                if backlog_before > 0:
                    _emit_external_repl_block(f"Queued message #{backlog_before} for session {active_session_id}.")
            except Exception as exc:
                import traceback
                traceback.print_exc()
                layer = _error_layer_for_exception(exc)
                suggestion = _suggestion_for_exception(
                    exc,
                    default="run /new to start a session, then retry.",
                )
                _print_repl_turn_error(
                    out=out,
                    error=RuntimeError(f"send failed: {exc}"),
                    layer=layer,
                    suggestion=suggestion,
                )
    finally:
        if run_queue is not None:
            run_queue.close(wait_for_drain=False)

def _send_message_from_repl(
    *,
    out: TextIO,
    client: ServerClient,
    session_id: str,
    text: str,
    preview_writer: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if not _supports_async_repl_events(client):
        return client.send_message(session_id=session_id, text=text)
    return _send_message_with_async_events(
        out=out,
        client=client,
        session_id=session_id,
        text=text,
        preview_writer=preview_writer,
    )


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


def _extract_message_content(payload: dict[str, object]) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content


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


def _resolve_initial_session_id() -> str | None:
    value = os.getenv("NANO_MULTIAGENT_SESSION_ID", "").strip()
    return value or None


def _extract_session_id(payload: dict[str, object]) -> str:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise RuntimeError("missing session_id in response")
    return session_id


def _prompt(active_session_id: str | None) -> str:
    if active_session_id:
        return f"[{active_session_id}]> "
    return "nano> "
