import json
from dataclasses import dataclass
from typing import Callable, Sequence, TextIO

from nano_multiagent.cli.http_client import ServerClient

_DEFAULT_HISTORY_LIMIT = 20
REPL_COMMANDS = ("/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit")
HELP_LINE = "Commands: /help /new /use <session_id> /session /tools /compact /history [n] /exit"


@dataclass(frozen=True, slots=True)
class ReplCommandResult:
    handled: bool
    active_session_id: str | None
    should_exit: bool = False


def handle_repl_command(
    *,
    line: str,
    out: TextIO,
    client: ServerClient,
    active_session_id: str | None,
    history_by_session: dict[str, list[tuple[str, str]]],
    extract_session_id: Callable[[dict[str, object]], str],
    print_tools_summary: Callable[..., None],
    print_compact_summary: Callable[..., None],
    print_context_budget_snapshot: Callable[..., None],
    layer_for_exception: Callable[[Exception], str],
    suggestion_for_exception: Callable[[Exception, str], str],
) -> ReplCommandResult:
    command, argument = _parse_command(line)
    argument_tokens = _split_argument_tokens(argument)

    if command == "/help":
        if argument_tokens:
            print_actionable_error(
                out=out,
                message="command /help does not accept arguments.",
                suggestion="try /help.",
                usage="/help",
            )
            return ReplCommandResult(handled=True, active_session_id=active_session_id)
        print(HELP_LINE, file=out)
        return ReplCommandResult(handled=True, active_session_id=active_session_id)

    if command == "/exit":
        if argument_tokens:
            print_actionable_error(
                out=out,
                message="command /exit does not accept arguments.",
                suggestion="try /exit.",
                usage="/exit",
            )
            return ReplCommandResult(handled=True, active_session_id=active_session_id)
        return ReplCommandResult(handled=True, active_session_id=active_session_id, should_exit=True)

    try:
        if command == "/new":
            if argument_tokens:
                print_actionable_error(
                    out=out,
                    message="command /new does not accept arguments.",
                    suggestion="try /new.",
                    usage="/new",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            payload = client.create_session()
            next_session_id = extract_session_id(payload)
            print(json.dumps(payload, ensure_ascii=False), file=out)
            return ReplCommandResult(handled=True, active_session_id=next_session_id)

        if command == "/use":
            if not argument_tokens:
                print_actionable_error(
                    out=out,
                    message="missing session_id for /use.",
                    suggestion="try /use <session_id>.",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            if len(argument_tokens) != 1:
                print_actionable_error(
                    out=out,
                    message="/use expects exactly one session_id.",
                    suggestion="try /use <session_id>.",
                    usage="/use <session_id>",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            next_session_id = argument_tokens[0]
            print(json.dumps({"session_id": next_session_id}, ensure_ascii=False), file=out)
            return ReplCommandResult(handled=True, active_session_id=next_session_id)

        if command == "/session":
            if argument_tokens:
                print_actionable_error(
                    out=out,
                    message="command /session does not accept arguments.",
                    suggestion="try /session.",
                    usage="/session",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            print(json.dumps({"session_id": active_session_id}, ensure_ascii=False), file=out)
            return ReplCommandResult(handled=True, active_session_id=active_session_id)

        if command == "/tools":
            if argument_tokens:
                print_actionable_error(
                    out=out,
                    message="command /tools does not accept arguments.",
                    suggestion="try /tools.",
                    usage="/tools",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            if not active_session_id:
                print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            payload = client.list_session_tools(session_id=active_session_id)
            print_tools_summary(out=out, payload=payload)
            return ReplCommandResult(handled=True, active_session_id=active_session_id)

        if command == "/compact":
            if argument_tokens:
                print_actionable_error(
                    out=out,
                    message="command /compact does not accept arguments.",
                    suggestion="try /compact.",
                    usage="/compact",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            if not active_session_id:
                print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            payload = client.compact_session(session_id=active_session_id)
            print_compact_summary(out=out, payload=payload)
            print_context_budget_snapshot(
                out=out,
                client=client,
                session_id=active_session_id,
                context_label="after /compact",
            )
            return ReplCommandResult(handled=True, active_session_id=active_session_id)

        if command == "/history":
            if len(argument_tokens) > 1:
                print_actionable_error(
                    out=out,
                    message="invalid n for /history.",
                    suggestion="try /history 10.",
                    usage="/history [n]",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            history_limit, error = _parse_history_limit(argument_tokens[0] if argument_tokens else None)
            if error is not None:
                print_actionable_error(
                    out=out,
                    message=error,
                    suggestion="try /history 10.",
                    usage="/history [n]",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            if not active_session_id:
                print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return ReplCommandResult(handled=True, active_session_id=active_session_id)
            _print_history(
                out=out,
                session_id=active_session_id,
                history=history_by_session.get(active_session_id, ()),
                limit=history_limit,
            )
            return ReplCommandResult(handled=True, active_session_id=active_session_id)
    except Exception as exc:
        print_actionable_error(
            out=out,
            message=f"failed to run {command}.",
            suggestion=suggestion_for_exception(exc, command),
            layer=layer_for_exception(exc),
        )
        return ReplCommandResult(handled=True, active_session_id=active_session_id)

    print_actionable_error(
        out=out,
        message=f"unknown command '{command}'.",
        suggestion="run /help to see available commands.",
    )
    return ReplCommandResult(handled=True, active_session_id=active_session_id)


def print_actionable_error(
    *,
    out: TextIO,
    message: str,
    suggestion: str,
    layer: str = "input",
    usage: str | None = None,
) -> None:
    print(f"Error: {message}", file=out)
    print(f"Layer: {layer}", file=out)
    print(f"Suggestion: {suggestion}", file=out)
    if usage is not None:
        print(f"Usage: {usage}", file=out)


def _split_argument_tokens(argument: str | None) -> list[str]:
    if argument is None:
        return []
    tokens = [token for token in argument.split() if token]
    return tokens


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


def _parse_command(line: str) -> tuple[str, str | None]:
    parts = line.split(maxsplit=1)
    command = parts[0]
    argument = parts[1].strip() if len(parts) == 2 else None
    return command, argument

