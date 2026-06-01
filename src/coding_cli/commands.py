"""CLI entry orchestration over in-process agent.sdk Kernel.

Architecture (refactor-387 M2):
- No HTTP, no spawned subprocess: Kernel assembled via agent.sdk.build_kernel().
- Async-native REPL: main loop is asyncio.run(repl_main()), matching PA and CC.
- Permission via can_use_tool callback: CLI awaits user input inside the callback,
  mirroring how PA uses a programmatic policy.
- Removed: --mode/--base-url, health/create-session/send-message HTTP subcommands,
  ManagedServerProcess/ServerClient usage.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

from coding_cli.events.background_runs import BackgroundRunEventProcessor
from coding_cli.events.event_pipeline import (
    build_repl_view_model as _build_repl_view_model,
)
from coding_cli.events.repl_events import _build_ordered_repl_updates
from coding_cli.events.repl_events import _event_preview_line
from coding_cli.events.repl_events import (
    merge_text_delta as _merge_text_delta,
)  # bridge: tested via module attr
from coding_cli.events.repl_events import (
    print_event_preview as _print_event_preview,
)  # bridge: tested via module attr
import coding_cli.input.repl_commands as repl_commands
import coding_cli.input.repl_input as repl_input
from coding_cli.render.context_budget import (
    context_budget_hint_for_ratio as _context_budget_hint_for_ratio,
)  # bridge
from coding_cli.render.context_budget import (
    context_budget_prefix as _context_budget_prefix,
)  # bridge
from coding_cli.render.context_budget import (
    extract_context_budget_metrics as _extract_context_budget_metrics,
)  # bridge
from coding_cli.render.context_budget import (
    print_context_budget_snapshot as _print_context_budget_snapshot,
)  # bridge
from coding_cli.render.error_presenter import (
    error_layer_for_exception as _error_layer_for_exception,
)
from coding_cli.render.error_presenter import (
    suggestion_for_exception as _suggestion_for_exception,
)
from coding_cli.render.repl_render import (
    print_repl_turn_error as _print_repl_turn_error,
)
from coding_cli.render.repl_render import (
    print_repl_turn_summary as _print_repl_turn_summary,
)
from coding_cli.render.terminal_output import emit_lines as _emit_terminal_lines
from coding_cli.render.terminal_output import write_tty_line as _write_tty_line

_CLI_HELP_EPILOG = (
    "REPL quick commands: /help /new /use <session_id> /session /tools /compact /history [n] /exit\n"
    "Inline editing: ←/→ move cursor, Backspace deletes at cursor.\n"
    "History recall: ↑/↓ navigates per-session input history and restores draft.\n"
    "In-process kernel: CLI holds Kernel directly via agent.sdk — no HTTP, no subprocess.\n"
    "Permission: prompted inline when agent needs tool confirmation.\n"
    "JSON contract: --text mode prints a single final JSON object on stdout.\n"
    "LLM usage: shown per turn when provider usage is available.\n"
    "Error layers: input / runtime."
)

_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}

# Test-injectable factory type: callable that returns a Kernel-compatible object.
KernelFactory = Callable[..., Any]


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


def build_parser() -> argparse.ArgumentParser:
    """Build command parser for async-native REPL and --text mode."""
    parser = argparse.ArgumentParser(
        prog="nano-multiagent-cli",
        description="Interactive Coding Agent CLI — in-process Kernel via agent.sdk.",
        epilog=_CLI_HELP_EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--request-id", default=None)
    parser.add_argument(
        "--resume",
        default=None,
        help="Resume an existing session by id in REPL or --text mode.",
    )
    parser.add_argument(
        "--model", dest="llm_model", default=None, help="LLM model to use."
    )
    parser.add_argument(
        "--provider", dest="llm_provider", default=None, help="LLM provider to use."
    )
    parser.add_argument(
        "--llm-base-url", dest="llm_base_url", default=None, help="LLM base URL."
    )
    parser.add_argument(
        "--api-key", dest="llm_api_key", default=None, help="LLM API key."
    )
    parser.add_argument(
        "--timeout-seconds",
        dest="llm_timeout_seconds",
        type=float,
        default=None,
        help="LLM timeout in seconds.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help=(
            "Non-interactive mode: submit text and stream NDJSON events to stdout, then exit."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    llm_parser = subparsers.add_parser("llm-config")
    llm_subparsers = llm_parser.add_subparsers(dest="llm_config_command", required=True)
    llm_subparsers.add_parser("get")
    llm_set_parser = llm_subparsers.add_parser("set")
    llm_set_parser.add_argument("--provider", dest="llm_config_provider", default=None)
    llm_set_parser.add_argument("--model", dest="llm_config_model", default=None)
    llm_set_parser.add_argument("--base-url", dest="llm_config_base_url", default=None)
    llm_set_parser.add_argument("--api-key", dest="llm_config_api_key", default=None)
    llm_set_parser.add_argument(
        "--clear-api-key", dest="llm_config_clear_api_key", action="store_true"
    )
    llm_set_parser.add_argument(
        "--timeout-seconds", dest="llm_config_timeout_seconds", type=float, default=None
    )

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    kernel_factory: KernelFactory | None = None,
    input_fn: Callable[[str], str] | None = None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None = None,
    workspace_root: Path | None = None,
) -> int:
    """Run CLI REPL or --text mode and return process exit code.

    The kernel is assembled in-process via agent.sdk.build_kernel() (or the
    injected kernel_factory for tests).  No HTTP server, no subprocess.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
        stdout: Output stream (defaults to sys.stdout).
        kernel_factory: Test-only factory returning a Kernel-compatible object
            without starting real LLM connections.
        input_fn: Synchronous line-reader for tests (overrides terminal input).
        repl_input_reader_factory: Factory for pluggable ReplInputReader.
        workspace_root: Override workspace root (tests only).

    Returns:
        Process exit code: 0 on success, 1 on error.

    Notes:
        JSON contract: non-interactive commands print exactly one JSON object
        to stdout, so scripts can parse results without REPL noise.
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out = stdout or sys.stdout
    resolved_root = workspace_root or Path(os.getcwd())

    try:
        return asyncio.run(
            _async_main(
                args=args,
                out=out,
                kernel_factory=kernel_factory,
                input_fn=input_fn,
                repl_input_reader_factory=repl_input_reader_factory,
                workspace_root=resolved_root,
            )
        )
    except Exception as exc:
        layer = _error_layer_for_exception(exc)
        suggestion = _suggestion_for_exception(
            exc, default="check configuration and retry."
        )
        print(
            json.dumps(
                {"error": str(exc), "layer": layer, "suggestion": suggestion},
                ensure_ascii=False,
            ),
            file=out,
        )
        return 1


async def _async_main(
    *,
    args: argparse.Namespace,
    out: TextIO,
    kernel_factory: KernelFactory | None,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None,
    workspace_root: Path,
) -> int:
    """Async entry: build Kernel, dispatch to REPL or --text mode."""
    kernel = _build_kernel(args=args, kernel_factory=kernel_factory, out=out)
    try:
        if args.text is not None:
            session = await kernel.create_session(workspace_root=workspace_root)
            session_id = args.resume.strip() if args.resume else session.session_id
            return await _run_text_mode(
                kernel=kernel,
                session_id=session_id,
                text=args.text,
                out=out,
                workspace_root=workspace_root,
            )

        if args.command == "llm-config":
            return _run_llm_config_command(args=args, kernel=kernel, out=out)

        # Default path: interactive REPL.
        return await _run_repl(
            args=args,
            out=out,
            kernel=kernel,
            input_fn=input_fn,
            repl_input_reader_factory=repl_input_reader_factory,
            workspace_root=workspace_root,
        )
    finally:
        kernel.close()


def _build_kernel(
    *,
    args: argparse.Namespace,
    kernel_factory: KernelFactory | None,
    out: TextIO,
) -> Any:
    """Assemble Kernel from agent.sdk or test-injected factory."""
    if kernel_factory is not None:
        return kernel_factory()

    # Production path: import agent.sdk and assemble the local_coding kernel.
    # All types used here are re-exported from agent.sdk — coding_cli only imports agent.sdk.
    from agent.sdk import build_kernel, LOCAL_CODING_PROFILE, init_model_registry

    # init_model_registry must be called before LLMFactoryConfig.from_env(), because
    # from_env() calls get_default_provider() which requires the registry to be populated.
    # This mirrors personal_assistant/main.py:1098 — products init the registry at
    # process startup before building the kernel.
    llm_payload = _build_llm_config_payload(args)
    init_model_registry(llm_payload)

    llm_config = _build_llm_config_from_args(args)

    # can_use_tool callback: runs in executor so it doesn't block the async loop.
    async def can_use_tool(tool_name: str, tool_input: Any, ctx: Any) -> Any:
        return await _ask_permission_async(
            tool_name=tool_name, tool_input=tool_input, out=out
        )

    return build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
        llm_config=llm_config,
        can_use_tool=can_use_tool,
    )


def _build_llm_config_payload(args: argparse.Namespace) -> Any:
    """Build LLMConfigPayload for init_model_registry from env vars and CLI overrides.

    Called before LLMFactoryConfig.from_env() so the registry is populated when
    from_env() calls get_default_provider().  Priority:
    1. NANO_MULTIAGENT_LLM_CONFIG_JSON env (full Gateway-style payload)
    2. Individual env vars + CLI args (minimal single-provider payload)

    Args:
        args: Parsed CLI arguments (may carry --provider/--model/--llm-base-url).

    Returns:
        LLMConfigPayload ready for init_model_registry().
    """
    from agent.sdk import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    # Fast path: full config JSON injected (e.g. from a parent process or test env).
    raw_json = os.getenv("NANO_MULTIAGENT_LLM_CONFIG_JSON")
    if raw_json:
        return LLMConfigPayload.from_json(raw_json)

    # Slow path: build minimal payload from env vars + CLI args.
    provider = getattr(args, "llm_provider", None) or os.getenv(
        "NANO_MULTIAGENT_LLM_PROVIDER", "anthropic"
    )
    model = getattr(args, "llm_model", None) or os.getenv(
        "NANO_MULTIAGENT_LLM_MODEL", "kimiCoding:K2.6"
    )
    base_url = getattr(args, "llm_base_url", None) or os.getenv(
        "NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000"
    )
    return LLMConfigPayload(
        default_model=model,
        providers=(
            LLMProviderPayload(
                name=provider,
                base_url=base_url,
                models=(LLMModelPayload(name=model),),
            ),
        ),
    )


def _build_llm_config_from_args(args: argparse.Namespace) -> Any:
    """Build LLMFactoryConfig from env vars layered with CLI overrides.

    Must be called after _build_llm_config_payload + init_model_registry, since
    LLMFactoryConfig.from_env() requires the registry to be initialized.
    """
    from agent.sdk import LLMFactoryConfig
    import dataclasses

    base = LLMFactoryConfig.from_env()
    kwargs: dict[str, Any] = {}
    if getattr(args, "llm_provider", None):
        kwargs["provider"] = args.llm_provider
    if getattr(args, "llm_model", None):
        kwargs["model"] = args.llm_model
    if getattr(args, "llm_base_url", None):
        kwargs["base_url"] = args.llm_base_url
    if getattr(args, "llm_api_key", None):
        kwargs["api_key"] = args.llm_api_key
    if getattr(args, "llm_timeout_seconds", None) is not None:
        kwargs["timeout_seconds"] = args.llm_timeout_seconds
    if not kwargs:
        return base
    return dataclasses.replace(base, **kwargs)


async def _ask_permission_async(
    *,
    tool_name: str,
    tool_input: Any,
    out: TextIO,
) -> Any:
    """Async permission callback: present picker and await user decision.

    Runs read_permission_choice in a thread executor so the event loop is
    not blocked while waiting for terminal input.
    """
    from agent.sdk import PermissionDecision

    options = [
        repl_input.PermissionOption(
            id="allow", label="Allow once", description="Allow this single action"
        ),
        repl_input.PermissionOption(
            id="deny", label="Deny", description="Block this action"
        ),
    ]
    header = f"Permission request: {tool_name}"
    if tool_input:
        try:
            header += f"\n  {json.dumps(tool_input, ensure_ascii=False)[:120]}"
        except Exception:
            pass

    loop = asyncio.get_event_loop()
    chosen_id = await loop.run_in_executor(
        None,
        lambda: repl_input.read_permission_choice(
            header=header, options=options, out=out
        ),
    )
    return PermissionDecision(behavior=chosen_id)


async def _run_text_mode(
    *,
    kernel: Any,
    session_id: str,
    text: str,
    out: TextIO,
    workspace_root: Path,
) -> int:
    """Non-interactive --text mode: submit once, stream NDJSON to stdout, exit.

    Returns:
        0 on completed run, 1 on failed/cancelled.
    """
    run_record = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=workspace_root,
    )
    run_id = run_record.run_id

    out.write(
        json.dumps({"event": "submit_response", "run_id": run_id}, ensure_ascii=False)
        + "\n"
    )
    _flush(out)

    final_status = "failed"
    async for event in kernel.stream(session_id):
        event_run_id = event.get("run_id")
        if event_run_id is not None and event_run_id != run_id:
            continue
        out.write(json.dumps(event, ensure_ascii=False) + "\n")
        _flush(out)
        if event.get("event") == "run_status":
            status = event.get("status", "")
            if status in _TERMINAL_STATUSES:
                final_status = status
                break

    return 0 if final_status == "completed" else 1


def _run_llm_config_command(
    *,
    args: argparse.Namespace,
    kernel: Any,
    out: TextIO,
) -> int:
    """Handle llm-config get/set subcommands via Kernel."""
    if args.llm_config_command == "get":
        config = kernel.get_llm_config()
        payload = {
            "provider": getattr(config, "provider", None),
            "model": getattr(config, "model", None),
            "base_url": getattr(config, "base_url", None),
            "timeout_seconds": getattr(config, "timeout_seconds", None),
        }
        print(json.dumps(payload, ensure_ascii=False), file=out)
        return 0

    # set subcommand
    provider = args.llm_config_provider
    model = args.llm_config_model
    base_url = args.llm_config_base_url
    api_key = args.llm_config_api_key
    clear_api_key = bool(getattr(args, "llm_config_clear_api_key", False))
    timeout_seconds = args.llm_config_timeout_seconds

    if api_key is not None and clear_api_key:
        raise ValueError(
            "--api-key and --clear-api-key cannot be used together — choose either"
        )
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be > 0")

    patch: dict[str, Any] = {}
    if provider is not None:
        if not provider.strip():
            raise ValueError("provider must be a non-empty string")
        patch["provider"] = provider.strip()
    if model is not None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        patch["model"] = model.strip()
    if base_url is not None:
        if not base_url.strip():
            raise ValueError("base_url must be a non-empty string")
        patch["base_url"] = base_url.strip()
    if api_key is not None:
        patch["api_key"] = api_key
    if clear_api_key:
        patch["api_key"] = None
    if timeout_seconds is not None:
        patch["timeout_seconds"] = timeout_seconds

    if not patch:
        raise ValueError(
            "llm-config set requires at least one field: "
            "--provider/--model/--base-url/--api-key/--clear-api-key/--timeout-seconds"
        )

    config = kernel.reconfigure_llm(**patch)
    payload = {
        "provider": getattr(config, "provider", None),
        "model": getattr(config, "model", None),
        "base_url": getattr(config, "base_url", None),
        "timeout_seconds": getattr(config, "timeout_seconds", None),
    }
    print(json.dumps(payload, ensure_ascii=False), file=out)
    return 0


async def _run_repl(
    *,
    args: argparse.Namespace,
    out: TextIO,
    kernel: Any,
    input_fn: Callable[[str], str] | None,
    repl_input_reader_factory: Callable[[], repl_input.ReplInputReader] | None,
    workspace_root: Path,
) -> int:
    """Async-native interactive REPL loop.

    submit()/interrupt() are sync non-blocking Kernel calls.  Session lifecycle
    and compact() are awaited.  The permission callback is wired at kernel-build
    time and invoked via SDK's permission bridge.
    """
    active_session_id: str | None = _resolve_initial_session_id(args)
    history_by_session: dict[str, list[tuple[str, str]]] = {}
    input_history_by_session: dict[str, list[str]] = {}

    if _is_tty_output(out):

        def _emit_repl_block(text: str) -> None:
            repl_input.emit_persistent_text(out=out, text=text)
    else:

        def _emit_repl_block(text: str) -> None:
            _emit_plain_repl_block(out=out, text=text)

    def _print_repl_turn_error_block(
        *, error: Exception, layer: str, suggestion: str
    ) -> None:
        buffer = io.StringIO()
        _print_repl_turn_error(
            out=buffer, error=error, layer=layer, suggestion=suggestion
        )
        _emit_repl_block(buffer.getvalue())

    # Auto mode startup banner (spec A2: dangerously_skip_permissions must be visible).
    _auto_config = _load_auto_mode_config_for_repl()
    _banner_buf = io.StringIO()
    print_auto_mode_banner(config=_auto_config, out=_banner_buf)
    _banner_text = _banner_buf.getvalue()
    if _banner_text.strip():
        _emit_repl_block(_banner_text)

    background_processor = BackgroundRunEventProcessor()

    # Background event queue: receives events from kernel stream for non-current
    # runs (e.g. background tasks completing after a user turn finishes).
    _bg_event_queue: asyncio.Queue = asyncio.Queue(maxsize=4096)

    # Background stream task: started when we have an active session.
    _stream_task: asyncio.Task | None = None

    async def _ensure_stream_for_session(session_id: str) -> None:
        nonlocal _stream_task
        # Cancel any existing stream task for a different session.
        if _stream_task is not None and not _stream_task.done():
            _stream_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_stream_task), timeout=0.3)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        async def _drain_forever(sid: str) -> None:
            try:
                async for ev in kernel.stream(sid):
                    try:
                        _bg_event_queue.put_nowait(ev)
                    except asyncio.QueueFull:
                        pass
            except asyncio.CancelledError:
                pass

        _stream_task = asyncio.create_task(_drain_forever(session_id))

    def _flush_bg_events() -> list[str]:
        """Drain background event queue, returning display lines."""
        lines: list[str] = []
        while True:
            try:
                ev = _bg_event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            lines.extend(background_processor.process(ev))
        return lines

    read_line = repl_input.build_repl_input_reader(
        out=out,
        input_fn=input_fn,
        repl_input_reader_factory=repl_input_reader_factory,
        command_suggestions=repl_commands.REPL_COMMANDS,
        on_idle=None,
        idle_interval_seconds=0.5,
    )

    try:
        while True:
            # Flush background events that arrived while idle.
            bg_lines = _flush_bg_events()
            if bg_lines:
                _emit_repl_block("\n".join(bg_lines))

            try:
                raw = read_line(
                    _prompt(active_session_id),
                    input_history_by_session.get(active_session_id or "", ()),
                )
            except EOFError:
                _emit_repl_block("bye")
                return 0

            line = raw.strip()
            if not line:
                continue

            if repl_commands.is_repl_command_candidate(line):
                if active_session_id:
                    _append_input_history_entry(
                        input_history_by_session, active_session_id, line
                    )

                cmd_result = await _handle_repl_command_async(
                    line=line,
                    out=out,
                    kernel=kernel,
                    active_session_id=active_session_id,
                    history_by_session=history_by_session,
                    workspace_root=workspace_root,
                )
                if cmd_result.new_session_id is not None:
                    active_session_id = cmd_result.new_session_id
                    await _ensure_stream_for_session(active_session_id)
                if cmd_result.should_exit:
                    return 0
                if cmd_result.handled:
                    continue

            try:
                if not active_session_id:
                    session = await kernel.create_session(workspace_root=workspace_root)
                    active_session_id = session.session_id
                    repl_commands.print_session_created(
                        out=out, session_id=active_session_id
                    )
                    repl_commands.print_active_session(
                        out=out, session_id=active_session_id
                    )
                    await _ensure_stream_for_session(active_session_id)

                _append_input_history_entry(
                    input_history_by_session, active_session_id, line
                )
                _append_history_entry(
                    history_by_session, active_session_id, role="user", content=line
                )

                payload = await _send_message_async(
                    out=out,
                    kernel=kernel,
                    session_id=active_session_id,
                    text=line,
                    workspace_root=workspace_root,
                    background_processor=background_processor,
                    bg_event_queue=_bg_event_queue,
                )

                response_content = _extract_message_content(payload)
                if response_content is not None:
                    _append_history_entry(
                        history_by_session,
                        active_session_id,
                        role="assistant",
                        content=response_content,
                    )

                buffer = io.StringIO()
                _print_repl_turn_summary(out=buffer, payload=payload)
                _emit_repl_block(buffer.getvalue())
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
        if _stream_task is not None and not _stream_task.done():
            _stream_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_stream_task), timeout=0.3)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


async def _send_message_async(
    *,
    out: TextIO,
    kernel: Any,
    session_id: str,
    text: str,
    workspace_root: Path,
    background_processor: BackgroundRunEventProcessor,
    bg_event_queue: asyncio.Queue,
) -> dict[str, object]:
    """Submit message, stream kernel events for this run, return turn payload.

    Events from other runs go to background_processor / bg_event_queue so they
    appear before the next prompt (design: background task completion notifications).
    """
    run_record = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=workspace_root,
    )
    run_id = run_record.run_id

    events: list[dict[str, Any]] = []
    assistant_text = ""
    terminal_run_status: dict[str, Any] | None = None
    live_rendered = _is_tty_output(out)

    _thinking_shown = [True]
    if live_rendered:
        print("⠋ Thinking...", end="\r", file=out, flush=True)

    def _erase_thinking() -> None:
        if _thinking_shown[0]:
            print("\r\033[K", end="", file=out, flush=True)
            _thinking_shown[0] = False

    from coding_cli.render.repl_tool_lines import format_tool_done, format_tool_running

    async for event in kernel.stream(session_id):
        event_run_id = event.get("run_id")

        # Route events from other runs to background processor.
        if event_run_id is not None and event_run_id != run_id:
            bg_lines = background_processor.process(event)
            if bg_lines:
                _erase_thinking()
                _emit_terminal_lines(out, bg_lines, is_tty=live_rendered)
            try:
                bg_event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
            continue

        events.append(event)
        event_name = event.get("event")

        if live_rendered:
            _erase_thinking()
            if event_name == "assistant_message":
                content = event.get("content") or ""
                if content:
                    lines = content.split("\n")
                    while lines and lines[-1] == "":
                        lines.pop()
                    for ln in lines:
                        _write_tty_line(out, f"> {ln}")
            elif event_name == "tool_start":
                name = str(event.get("name") or "?")
                print(format_tool_running(name), end="\r", file=out, flush=True)
            elif event_name == "tool_end":
                name = str(event.get("name") or "?")
                duration_ms = event.get("duration_ms")
                out.write(f"\r\033[K{format_tool_done(name, duration_ms)}\r\n")
                out.flush()
        else:
            # Non-TTY path: print tool_start and tool_exec_started immediately so
            # tool start lines appear in order (mirrors the old drain_run behavior).
            if event_name in ("tool_start", "tool_exec_started"):
                preview_line = _event_preview_line(event_name=event_name, data=event)
                if preview_line:
                    print(preview_line, file=out)

        if event_name == "assistant_message":
            assistant_text = event.get("content") or ""

        if event_name == "run_status":
            status = event.get("status", "")
            if status in _TERMINAL_STATUSES:
                terminal_run_status = event
                break

    if live_rendered:
        _erase_thinking()

    status = "unknown"
    stop_reason = None
    usage = None
    if terminal_run_status is not None:
        status = terminal_run_status.get("status") or status
        stop_reason = terminal_run_status.get("stop_reason")
        usage = terminal_run_status.get("usage")

    if status not in ("completed",):
        error_detail = assistant_text.strip()
        if error_detail:
            raise RuntimeError(f"run_id={run_id} run failed: {error_detail}")
        raise RuntimeError(f"run_id={run_id} run failed")

    # Build view model matching existing repl_render expectations.
    legacy_events: list[tuple[str, dict[str, object]]] = []
    for ev in events:
        ev_name = ev.get("event")
        data = dict(ev)
        data.pop("event", None)
        if ev_name == "assistant_message":
            ev_name = "text_delta"
            data["delta"] = data.pop("content", "")
        legacy_events.append((ev_name, data))

    view_model = _build_repl_view_model(
        events=legacy_events,
        preview_line_resolver=lambda name, data: _event_preview_line(
            event_name=name, data=data
        ),
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


# ---------------------------------------------------------------------------
# Async REPL command handling
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _ReplCommandResult:
    handled: bool
    # None means no session change; non-None replaces active_session_id.
    new_session_id: str | None = None
    should_exit: bool = False


async def _handle_repl_command_async(
    *,
    line: str,
    out: TextIO,
    kernel: Any,
    active_session_id: str | None,
    history_by_session: dict[str, list[tuple[str, str]]],
    workspace_root: Path,
) -> _ReplCommandResult:
    """Handle slash commands, calling async Kernel methods as needed."""
    command, argument = _parse_command(line)
    argument_tokens = _split_argument_tokens(argument)

    if command == "/help":
        if argument_tokens:
            repl_commands.print_actionable_error(
                out=out,
                message="command /help does not accept arguments.",
                suggestion="try /help.",
                usage="/help",
            )
            return _ReplCommandResult(handled=True)
        print(repl_commands.HELP_LINE, file=out)
        return _ReplCommandResult(handled=True)

    if command == "/exit":
        return _ReplCommandResult(handled=True, should_exit=True)

    try:
        if command == "/new":
            if argument_tokens:
                repl_commands.print_actionable_error(
                    out=out,
                    message="command /new does not accept arguments.",
                    suggestion="try /new.",
                    usage="/new",
                )
                return _ReplCommandResult(handled=True)
            session = await kernel.create_session(
                workspace_root=workspace_root, skills=[]
            )
            next_id = session.session_id
            repl_commands.print_session_created(out=out, session_id=next_id)
            repl_commands.print_active_session(out=out, session_id=next_id)
            return _ReplCommandResult(handled=True, new_session_id=next_id)

        if command == "/use":
            if not argument_tokens:
                repl_commands.print_actionable_error(
                    out=out,
                    message="missing session_id for /use.",
                    suggestion="try /use <session_id>.",
                )
                return _ReplCommandResult(handled=True)
            if len(argument_tokens) != 1:
                repl_commands.print_actionable_error(
                    out=out,
                    message="/use expects exactly one session_id.",
                    suggestion="try /use <session_id>.",
                    usage="/use <session_id>",
                )
                return _ReplCommandResult(handled=True)
            next_id = argument_tokens[0]
            repl_commands.print_session_switched(out=out, session_id=next_id)
            repl_commands.print_active_session(out=out, session_id=next_id)
            return _ReplCommandResult(handled=True, new_session_id=next_id)

        if command == "/session":
            if argument_tokens:
                repl_commands.print_actionable_error(
                    out=out,
                    message="command /session does not accept arguments.",
                    suggestion="try /session.",
                    usage="/session",
                )
                return _ReplCommandResult(handled=True)
            repl_commands.print_active_session(out=out, session_id=active_session_id)
            return _ReplCommandResult(handled=True)

        if command == "/tools":
            if argument_tokens:
                repl_commands.print_actionable_error(
                    out=out,
                    message="command /tools does not accept arguments.",
                    suggestion="try /tools.",
                    usage="/tools",
                )
                return _ReplCommandResult(handled=True)
            if not active_session_id:
                repl_commands.print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return _ReplCommandResult(handled=True)
            tools_info = kernel.list_session_tools(
                active_session_id, workspace_root=workspace_root
            )
            _print_tools_summary(out=out, payload=tools_info)
            return _ReplCommandResult(handled=True)

        if command == "/compact":
            if argument_tokens:
                repl_commands.print_actionable_error(
                    out=out,
                    message="command /compact does not accept arguments.",
                    suggestion="try /compact.",
                    usage="/compact",
                )
                return _ReplCommandResult(handled=True)
            if not active_session_id:
                repl_commands.print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return _ReplCommandResult(handled=True)
            result = await kernel.compact(
                active_session_id, workspace_root=workspace_root
            )
            _print_compact_summary(
                out=out,
                payload=result if isinstance(result, dict) else {"compacted": False},
                session_id=active_session_id,
            )
            return _ReplCommandResult(handled=True)

        if command == "/history":
            if len(argument_tokens) > 1:
                repl_commands.print_actionable_error(
                    out=out,
                    message="invalid n for /history.",
                    suggestion="try /history 10.",
                    usage="/history [n]",
                )
                return _ReplCommandResult(handled=True)
            # Validate limit before checking session — keeps error priority consistent.
            limit = 20
            if argument_tokens:
                try:
                    limit = int(argument_tokens[0])
                    if limit <= 0:
                        raise ValueError()
                except ValueError:
                    repl_commands.print_actionable_error(
                        out=out,
                        message="invalid n for /history.",
                        suggestion="try /history 10.",
                        usage="/history [n]",
                    )
                    return _ReplCommandResult(handled=True)
            if not active_session_id:
                repl_commands.print_actionable_error(
                    out=out,
                    message="no active session.",
                    suggestion="run /new or /use <session_id>.",
                )
                return _ReplCommandResult(handled=True)
            history = history_by_session.get(active_session_id, ())
            total = len(history)
            shown = list(history[-limit:])
            if not shown:
                print(f"History for session {active_session_id} is empty.", file=out)
            else:
                print(
                    f"History for session {active_session_id} (last {len(shown)}/{total}):",
                    file=out,
                )
                for role, content in shown:
                    print(f"{role}: {content}", file=out)
            return _ReplCommandResult(handled=True)

    except Exception as exc:
        layer = _error_layer_for_exception(exc, default="runtime")
        repl_commands.print_actionable_error(
            out=out,
            message=f"failed to run {command}.",
            suggestion=_suggestion_for_exception(
                exc, default=f"check configuration and retry {command}."
            ),
            layer=layer,
        )
        return _ReplCommandResult(handled=True)

    repl_commands.print_actionable_error(
        out=out,
        message=f"unknown command '{command}'.",
        suggestion="run /help to see available commands.",
    )
    return _ReplCommandResult(handled=True)


# ---------------------------------------------------------------------------
# Auto mode banner (spec A2 compliance)
# ---------------------------------------------------------------------------


def print_auto_mode_banner(*, config: object, out: TextIO) -> None:
    """Print the auto mode status banner at REPL startup.

    Why this is necessary: spec A2 requires that dangerously_skip_permissions being
    enabled must be visible to the user. CC surfaces this via a persistent status bar
    in its React UI; the Python REPL equivalent is a startup print so the state is
    never silently active.

    Args:
        config: AutoModeConfig-compatible object with .enabled and
            .dangerously_skip_permissions attributes.
        out: Output stream.
    """
    enabled: bool = getattr(config, "enabled", True)
    dangerously_skip: bool = getattr(config, "dangerously_skip_permissions", False)

    if dangerously_skip:
        print(
            "⚠ WARNING: dangerously_skip_permissions is enabled — all permission checks are bypassed.",
            file=out,
        )
        print(
            "  No tool will be blocked. This is only safe in isolated sandbox environments.",
            file=out,
        )
    elif enabled:
        print(
            "✓ Auto mode enabled — permission decisions handled automatically.",
            file=out,
        )
    else:
        print(
            "ℹ Auto mode disabled — manual approval required for tool actions.",
            file=out,
        )


def _load_auto_mode_config_for_repl() -> object:
    """Load auto mode config for REPL startup banner without cross-package imports.

    Reads the auto_mode section from the two-level config chain (workspace > global).
    Falls back to safe defaults on any error — must never crash the REPL.
    """
    import yaml

    class _AutoModeSummary:
        def __init__(self, enabled: bool, dangerously_skip_permissions: bool) -> None:
            self.enabled = enabled
            self.dangerously_skip_permissions = dangerously_skip_permissions

    def _read_section(config_path: Path) -> dict:
        if not config_path.is_file():
            return {}
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                section = raw.get("auto_mode", {})
                if isinstance(section, dict):
                    return section
        except Exception:
            pass
        return {}

    global_config_file = Path.home() / ".nanocode" / "config.yaml"
    workspace_config_file = Path.cwd() / ".nanocode" / "config.yaml"

    merged: dict = dict(_read_section(global_config_file))
    merged.update(_read_section(workspace_config_file))

    enabled: bool = True
    dangerously_skip: bool = False
    if isinstance(merged.get("enabled"), bool):
        enabled = merged["enabled"]
    if isinstance(merged.get("dangerously_skip_permissions"), bool):
        dangerously_skip = merged["dangerously_skip_permissions"]

    return _AutoModeSummary(
        enabled=enabled, dangerously_skip_permissions=dangerously_skip
    )


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def _print_tools_summary(*, out: TextIO, payload: Any) -> None:
    """Print tool list from SDK list_session_tools result."""
    if isinstance(payload, dict):
        session_id = payload.get("session_id", "<unknown>")
        items = payload.get("tools") or []
    else:
        session_id = "<unknown>"
        items = getattr(payload, "tools", []) or []

    resolved_session_id = str(session_id) if session_id else "<unknown>"
    items_list = list(items) if items else []
    print(f"Tools for session {resolved_session_id} ({len(items_list)}):", file=out)
    if not items_list:
        print("- (no tools)", file=out)
        return
    for tool in items_list:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        description = tool.get("description")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        resolved_description = (
            str(description)
            if isinstance(description, str) and description.strip()
            else "(no description)"
        )
        print(f"- {resolved_name}: {resolved_description}", file=out)


def _print_compact_summary(*, out: TextIO, payload: Any, session_id: str) -> None:
    """Print compaction result."""
    if isinstance(payload, dict):
        compacted = payload.get("compacted")
        result = payload.get("result")
    else:
        compacted = getattr(payload, "compacted", None)
        result = getattr(payload, "result", None)

    if compacted is not True or not isinstance(result, dict):
        print(f"Compaction for session {session_id}: no changes.", file=out)
        return
    print(f"Compaction for session {session_id}: compacted.", file=out)
    reason = result.get("reason")
    summary_text = result.get("summary")
    if isinstance(reason, str) and reason.strip():
        print(f"Reason: {reason}", file=out)
    if isinstance(summary_text, str) and summary_text.strip():
        print(f"Summary: {summary_text}", file=out)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def _resolve_initial_session_id(args: argparse.Namespace) -> str | None:
    value = getattr(args, "resume", None) or ""
    return value.strip() or None


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


def _parse_command(line: str) -> tuple[str, str | None]:
    parts = line.split(maxsplit=1)
    command = parts[0]
    argument = parts[1].strip() if len(parts) == 2 else None
    return command, argument


def _split_argument_tokens(argument: str | None) -> list[str]:
    if argument is None:
        return []
    return [token for token in argument.split() if token]


def _prompt(active_session_id: str | None) -> str:
    if active_session_id:
        return f"[{active_session_id}]> "
    return "nano> "


def _flush(out: TextIO) -> None:
    """Flush output if the stream supports it."""
    flush_fn = getattr(out, "flush", None)
    if callable(flush_fn):
        flush_fn()


from coding_cli.render.repl_summary import _extract_message_content
