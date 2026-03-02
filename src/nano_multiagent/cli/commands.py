import argparse
import json
import os
import sys
from typing import Callable, Sequence, TextIO

from nano_multiagent.cli.http_client import ServerClient, ServerClientConfig

_DEFAULT_HISTORY_LIMIT = 20
_REPL_COMMANDS = ("/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit")
_HELP_LINE = "Commands: /help /new /use <session_id> /session /tools /compact /history [n] /exit"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nano-multiagent-cli")
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
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out = stdout or sys.stdout

    env_config = ServerClientConfig.from_env()
    config = ServerClientConfig(
        base_url=args.base_url or env_config.base_url,
        token=args.token if args.token is not None else env_config.token,
        request_id=args.request_id if args.request_id is not None else env_config.request_id,
        timeout_seconds=env_config.timeout_seconds,
    )

    factory = client_factory or (lambda cfg: ServerClient(config=cfg))

    try:
        with factory(config) as client:
            if args.command is None:
                return _run_repl(
                    out=out,
                    client=client,
                    input_fn=input_fn or input,
                )
            payload = _run_single_command(args=args, client=client)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=out)
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
            if command == "/help":
                print(_HELP_LINE, file=out)
                continue
            if command == "/exit":
                return 0
            if command == "/new":
                payload = client.create_session()
                active_session_id = _extract_session_id(payload)
                print(json.dumps(payload, ensure_ascii=False), file=out)
                continue
            if command == "/use":
                if not argument:
                    print(json.dumps({"error": "usage: /use <session_id>"}, ensure_ascii=False), file=out)
                    continue
                active_session_id = argument
                print(json.dumps({"session_id": active_session_id}, ensure_ascii=False), file=out)
                continue
            if command == "/session":
                print(json.dumps({"session_id": active_session_id}, ensure_ascii=False), file=out)
                continue
            if command == "/tools":
                if not active_session_id:
                    print(json.dumps({"error": "no active session, use /new or /use <session_id>"}, ensure_ascii=False), file=out)
                    continue
                payload = client.list_session_tools(session_id=active_session_id)
                print(json.dumps(payload, ensure_ascii=False), file=out)
                continue
            if command == "/compact":
                if not active_session_id:
                    print(json.dumps({"error": "no active session, use /new or /use <session_id>"}, ensure_ascii=False), file=out)
                    continue
                payload = client.compact_session(session_id=active_session_id)
                print(json.dumps(payload, ensure_ascii=False), file=out)
                continue
            if command == "/history":
                if not active_session_id:
                    print(json.dumps({"error": "no active session, use /new or /use <session_id>"}, ensure_ascii=False), file=out)
                    continue
                history_limit, error = _parse_history_limit(argument)
                if error is not None:
                    print(json.dumps({"error": error}, ensure_ascii=False), file=out)
                    continue
                _print_history(
                    out=out,
                    session_id=active_session_id,
                    history=history_by_session.get(active_session_id, ()),
                    limit=history_limit,
                )
                continue
            print(json.dumps({"error": f"unknown command: {command}"}, ensure_ascii=False), file=out)
            continue

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


def _parse_history_limit(argument: str | None) -> tuple[int, str | None]:
    if argument is None:
        return _DEFAULT_HISTORY_LIMIT, None
    try:
        value = int(argument)
    except ValueError:
        return 0, "usage: /history [n], n must be a positive integer"
    if value <= 0:
        return 0, "usage: /history [n], n must be a positive integer"
    return value, None


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
