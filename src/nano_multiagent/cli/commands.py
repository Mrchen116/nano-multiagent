import argparse
import json
import os
import sys
from contextlib import nullcontext
from typing import Callable, Sequence, TextIO

from nano_multiagent.cli.http_client import ServerClient, ServerClientConfig
from nano_multiagent.cli.managed_server import ManagedServerConfig, ManagedServerProcess

_DEFAULT_HISTORY_LIMIT = 20
_REPL_COMMANDS = ("/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit")
_HELP_LINE = "Commands: /help /new /use <session_id> /session /tools /compact /history [n] /exit"
_DEFAULT_CLI_MODE = "remote"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nano-multiagent-cli")
    parser.add_argument("--mode", choices=("managed", "remote"), default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--request-id", default=None)

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("health")

    create_parser = subparsers.add_parser("create-session")
    create_parser.add_argument("--title", default=None)

    send_parser = subparsers.add_parser("send-message")
    send_parser.add_argument("--session-id", default=None)
    send_parser.add_argument("--text", required=True)

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    client_factory: Callable[[ServerClientConfig], ServerClient] | None = None,
    input_fn: Callable[[str], str] | None = None,
    managed_server_factory: Callable[[ManagedServerConfig], ManagedServerProcess] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out = stdout or sys.stdout
    mode = _DEFAULT_CLI_MODE

    try:
        mode = _resolve_mode(args.mode)
        env_config = ServerClientConfig.from_env()
        base_url = _resolve_base_url(mode=mode, arg_base_url=args.base_url, env_config=env_config)
        config = ServerClientConfig(
            base_url=base_url,
            token=args.token if args.token is not None else env_config.token,
            request_id=args.request_id if args.request_id is not None else env_config.request_id,
            timeout_seconds=env_config.timeout_seconds,
        )

        factory = client_factory or (lambda cfg: ServerClient(config=cfg))
        managed_factory = managed_server_factory or (lambda cfg: ManagedServerProcess(config=cfg))
        lifecycle = _build_server_lifecycle(mode=mode, config=config, managed_server_factory=managed_factory)
        with lifecycle:
            with factory(config) as client:
                if args.command is None:
                    return _run_repl(
                        out=out,
                        client=client,
                        input_fn=input_fn or input,
                    )
                payload = _run_single_command(args=args, client=client)
    except Exception as exc:
        suggestion = _suggestion_for_exception(
            exc,
            default=(
                "check local managed API startup and retry, or switch to --mode remote."
                if mode == "managed"
                else "check --base-url/--token and ensure remote API server is reachable."
            ),
        )
        print(json.dumps({"error": str(exc), "suggestion": suggestion}, ensure_ascii=False), file=out)
        return 1

    print(json.dumps(payload, ensure_ascii=False), file=out)
    return 0


def supported_repl_commands() -> tuple[str, ...]:
    return _REPL_COMMANDS


def _run_single_command(*, args: argparse.Namespace, client: ServerClient) -> dict[str, object]:
    if args.command == "health":
        return client.health()
    if args.command == "create-session":
        return client.create_session(title=args.title)
    session_id = args.session_id or os.getenv("NANO_MULTIAGENT_SESSION_ID")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session id is required: use --session-id or NANO_MULTIAGENT_SESSION_ID")
    return client.send_message(session_id=session_id, text=args.text)


def _run_repl(
    *,
    out: TextIO,
    client: ServerClient,
    input_fn: Callable[[str], str],
) -> int:
    active_session_id = _resolve_initial_session_id()
    history_by_session: dict[str, list[tuple[str, str]]] = {}
    while True:
        try:
            raw = input_fn(_prompt(active_session_id))
        except EOFError:
            print("bye", file=out)
            return 0

        line = raw.strip()
        if not line:
            continue

        if line.startswith("/"):
            command, argument = _parse_command(line)
            argument_tokens = _split_argument_tokens(argument)
            if command == "/help":
                if argument_tokens:
                    _print_actionable_error(
                        out=out,
                        message="command /help does not accept arguments.",
                        suggestion="try /help.",
                        usage="/help",
                    )
                    continue
                print(_HELP_LINE, file=out)
                continue
            if command == "/exit":
                if argument_tokens:
                    _print_actionable_error(
                        out=out,
                        message="command /exit does not accept arguments.",
                        suggestion="try /exit.",
                        usage="/exit",
                    )
                    continue
                return 0
            try:
                if command == "/new":
                    if argument_tokens:
                        _print_actionable_error(
                            out=out,
                            message="command /new does not accept arguments.",
                            suggestion="try /new.",
                            usage="/new",
                        )
                        continue
                    payload = client.create_session()
                    active_session_id = _extract_session_id(payload)
                    print(json.dumps(payload, ensure_ascii=False), file=out)
                    continue
                if command == "/use":
                    if not argument_tokens:
                        _print_actionable_error(
                            out=out,
                            message="missing session_id for /use.",
                            suggestion="try /use <session_id>.",
                        )
                        continue
                    if len(argument_tokens) != 1:
                        _print_actionable_error(
                            out=out,
                            message="/use expects exactly one session_id.",
                            suggestion="try /use <session_id>.",
                            usage="/use <session_id>",
                        )
                        continue
                    active_session_id = argument_tokens[0]
                    print(json.dumps({"session_id": active_session_id}, ensure_ascii=False), file=out)
                    continue
                if command == "/session":
                    if argument_tokens:
                        _print_actionable_error(
                            out=out,
                            message="command /session does not accept arguments.",
                            suggestion="try /session.",
                            usage="/session",
                        )
                        continue
                    print(json.dumps({"session_id": active_session_id}, ensure_ascii=False), file=out)
                    continue
                if command == "/tools":
                    if argument_tokens:
                        _print_actionable_error(
                            out=out,
                            message="command /tools does not accept arguments.",
                            suggestion="try /tools.",
                            usage="/tools",
                        )
                        continue
                    if not active_session_id:
                        _print_actionable_error(
                            out=out,
                            message="no active session.",
                            suggestion="run /new or /use <session_id>.",
                        )
                        continue
                    payload = client.list_session_tools(session_id=active_session_id)
                    _print_tools_summary(out=out, payload=payload)
                    continue
                if command == "/compact":
                    if argument_tokens:
                        _print_actionable_error(
                            out=out,
                            message="command /compact does not accept arguments.",
                            suggestion="try /compact.",
                            usage="/compact",
                        )
                        continue
                    if not active_session_id:
                        _print_actionable_error(
                            out=out,
                            message="no active session.",
                            suggestion="run /new or /use <session_id>.",
                        )
                        continue
                    payload = client.compact_session(session_id=active_session_id)
                    _print_compact_summary(out=out, payload=payload)
                    continue
                if command == "/history":
                    if len(argument_tokens) > 1:
                        _print_actionable_error(
                            out=out,
                            message="invalid n for /history.",
                            suggestion="try /history 10.",
                            usage="/history [n]",
                        )
                        continue
                    history_limit, error = _parse_history_limit(argument_tokens[0] if argument_tokens else None)
                    if error is not None:
                        _print_actionable_error(
                            out=out,
                            message=error,
                            suggestion="try /history 10.",
                            usage="/history [n]",
                        )
                        continue
                    if not active_session_id:
                        _print_actionable_error(
                            out=out,
                            message="no active session.",
                            suggestion="run /new or /use <session_id>.",
                        )
                        continue
                    _print_history(
                        out=out,
                        session_id=active_session_id,
                        history=history_by_session.get(active_session_id, ()),
                        limit=history_limit,
                    )
                    continue
            except Exception as exc:
                suggestion = _suggestion_for_exception(
                    exc,
                    default=f"check server status/token and retry {command}.",
                )
                _print_actionable_error(out=out, message=f"failed to run {command}.", suggestion=suggestion)
                continue

            _print_actionable_error(
                out=out,
                message=f"unknown command '{command}'.",
                suggestion="run /help to see available commands.",
            )
            continue

        try:
            if not active_session_id:
                session_payload = client.create_session()
                active_session_id = _extract_session_id(session_payload)
                print(json.dumps(session_payload, ensure_ascii=False), file=out)

            payload = client.send_message(session_id=active_session_id, text=line)
            _append_history_entry(history_by_session, active_session_id, role="user", content=line)
            response_content = _extract_message_content(payload)
            if response_content is not None:
                _append_history_entry(
                    history_by_session,
                    active_session_id,
                    role="assistant",
                    content=response_content,
                )
            print(json.dumps(payload, ensure_ascii=False), file=out)
        except Exception as exc:
            suggestion = _suggestion_for_exception(
                exc,
                default="run /new to start a session, then retry.",
            )
            _print_actionable_error(
                out=out,
                message=f"send failed: {exc}",
                suggestion=suggestion,
            )


def _parse_history_limit(argument: str | None) -> tuple[int, str | None]:
    if argument is None:
        return _DEFAULT_HISTORY_LIMIT, None
    try:
        value = int(argument)
    except ValueError:
        return 0, "invalid n for /history."
    if value <= 0:
        return 0, "invalid n for /history."
    return value, None


def _suggestion_for_exception(exc: Exception, *, default: str) -> str:
    explicit_suggestion = getattr(exc, "suggestion", None)
    if isinstance(explicit_suggestion, str) and explicit_suggestion.strip():
        return explicit_suggestion
    text = str(exc).lower()
    if "port" in text and "in use" in text:
        return "free the port, choose another local --base-url, or switch to --mode remote."
    if "remote mode requires --base-url" in text:
        return "pass --base-url <url> (or set NANO_MULTIAGENT_API_BASE_URL)."
    if "managed mode requires" in text:
        return "use a local http:// base URL for managed mode, or switch to --mode remote."
    if "connection refused" in text or "connecterror" in text or "nodename nor servname" in text:
        return "check --base-url and ensure API server is running."
    if "missing api token" in text or "unauthorized" in text or "401" in text:
        return "check --token or NANO_MULTIAGENT_API_TOKEN and retry."
    return default


def _resolve_mode(raw_mode: str | None) -> str:
    value = raw_mode or os.getenv("NANO_MULTIAGENT_CLI_MODE") or _DEFAULT_CLI_MODE
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
    value = arg_base_url or env_base_url or env_config.base_url
    return value.strip()


def _build_server_lifecycle(
    *,
    mode: str,
    config: ServerClientConfig,
    managed_server_factory: Callable[[ManagedServerConfig], ManagedServerProcess],
):
    if mode == "remote":
        return nullcontext()
    managed_server = managed_server_factory(
        ManagedServerConfig(
            base_url=config.base_url,
            token=config.token,
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


def _split_argument_tokens(argument: str | None) -> list[str]:
    if argument is None:
        return []
    tokens = [token for token in argument.split() if token]
    return tokens


def _print_history(
    *,
    out: TextIO,
    session_id: str,
    history: Sequence[tuple[str, str]],
    limit: int,
) -> None:
    total = len(history)
    if total == 0:
        print(f"History for session {session_id} is empty.", file=out)
        return
    shown = list(history[-limit:])
    print(f"History for session {session_id} (last {len(shown)}/{total}):", file=out)
    for role, content in shown:
        print(f"{role}: {content}", file=out)


def _append_history_entry(
    history_by_session: dict[str, list[tuple[str, str]]],
    session_id: str,
    *,
    role: str,
    content: str,
) -> None:
    entries = history_by_session.setdefault(session_id, [])
    entries.append((role, content))


def _extract_message_content(payload: dict[str, object]) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content


def _print_actionable_error(
    *,
    out: TextIO,
    message: str,
    suggestion: str,
    usage: str | None = None,
) -> None:
    print(f"Error: {message}", file=out)
    print(f"Suggestion: {suggestion}", file=out)
    if usage is not None:
        print(f"Usage: {usage}", file=out)


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


def _parse_command(line: str) -> tuple[str, str | None]:
    parts = line.split(maxsplit=1)
    command = parts[0]
    argument = parts[1].strip() if len(parts) == 2 else None
    return command, argument


def _prompt(active_session_id: str | None) -> str:
    if active_session_id:
        return f"[{active_session_id}]> "
    return "nano> "
