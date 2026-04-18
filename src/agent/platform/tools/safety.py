"""Sandbox and command policy primitives used by file/shell tools."""

import os
import selectors
import shlex
import subprocess
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.core.errors import ToolError

from .constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES


@dataclass(frozen=True, slots=True)
class ToolSafetyConfig:
    """Configure read/bash output limits and command policy guardrails."""

    read_max_lines: int = DEFAULT_MAX_LINES
    read_max_bytes: int = DEFAULT_MAX_BYTES
    bash_max_output_lines: int = DEFAULT_MAX_LINES
    bash_max_output_bytes: int = DEFAULT_MAX_BYTES
    bash_default_timeout: float = 30.0
    # Prefix-based allow list used after splitting command by "&&" segments.
    bash_allowed_prefixes: tuple[str, ...] = (
        "bash",
        "cat",
        "command -v",
        "echo",
        "false",
        "git",
        "head",
        "ls",
        "pwd",
        "pytest",
        "python",
        "python3",
        "rg",
        "sed",
        "sleep",
        "tail",
        "true",
        "wc",
    )
    # Backward-compatible executable allow-list; merged into prefixes at runtime.
    bash_allowed_commands: tuple[str, ...] = ()
    bash_blocked_fragments: tuple[str, ...] = (
        ":(){",
        "mkfs",
        "reboot",
        "rm -rf /",
        "shutdown",
    )


@dataclass(frozen=True, slots=True)
class CommandPolicyDecision:
    """Capture command policy decision before shell execution."""

    status: str
    details: Mapping[str, Any]


def load_tool_safety_config(*, repo_root: Path, default: ToolSafetyConfig | None = None) -> ToolSafetyConfig:
    """Load optional `.nano/policy.toml` overrides for tool safety."""

    base = default or ToolSafetyConfig()
    policy_path = (repo_root / ".nano" / "policy.toml").expanduser().resolve()
    if not policy_path.is_file():
        return base

    loaded = tomllib.loads(policy_path.read_text(encoding="utf-8"))
    bash_policy = _read_bash_policy_table(loaded)
    if not bash_policy:
        return base

    allowed_prefixes = _read_optional_string_tuple(bash_policy.get("allow_prefixes"))
    blocked_fragments = _read_optional_string_tuple(bash_policy.get("deny_fragments"))

    return ToolSafetyConfig(
        read_max_lines=base.read_max_lines,
        read_max_bytes=base.read_max_bytes,
        bash_max_output_lines=base.bash_max_output_lines,
        bash_max_output_bytes=base.bash_max_output_bytes,
        bash_default_timeout=base.bash_default_timeout,
        bash_allowed_prefixes=allowed_prefixes or base.bash_allowed_prefixes,
        bash_allowed_commands=base.bash_allowed_commands,
        bash_blocked_fragments=blocked_fragments or base.bash_blocked_fragments,
    )


def _read_bash_policy_table(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    direct = raw.get("bash")
    if isinstance(direct, Mapping):
        return direct
    tools_section = raw.get("tools")
    if not isinstance(tools_section, Mapping):
        return None
    nested = tools_section.get("bash")
    if not isinstance(nested, Mapping):
        return None
    return nested


def _read_optional_string_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped:
            normalized.append(stripped)
    if not normalized:
        return None
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class CommandExecution:
    """Capture normalized command execution output after truncation policy."""

    exit_code: int
    text: str
    truncated: bool
    full_output_path: str | None = None
    timed_out: bool = False
    aborted: bool = False
    timeout: float | None = None


class ToolSafety:
    """Enforce filesystem and shell guardrails for tool execution."""

    def __init__(self, *, repo_root: Path, config: ToolSafetyConfig) -> None:
        self.repo_root = repo_root
        self.config = config

    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path and require it to stay inside the repository root."""

        return self._resolve_path(
            path,
            cwd=cwd,
            tool_name=tool_name,
            allowed_roots=(self.repo_root,),
        )

    def resolve_read_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a read path under repository root or trusted shared skills root."""

        return self._resolve_path(
            path,
            cwd=cwd,
            tool_name=tool_name,
            allowed_roots=self._read_allowed_roots(),
        )

    def _resolve_path(
        self,
        path: str,
        *,
        cwd: Path,
        tool_name: str,
        allowed_roots: tuple[Path, ...],
    ) -> Path:
        # SECURITY BOUNDARY: all file tool paths are normalized and checked by
        # `relative_to` before use, so symlink/`..` traversal cannot escape roots.
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        resolved = candidate.resolve()
        for root in allowed_roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise ToolError(
            "path is outside repo sandbox",
            tool_name=tool_name,
            details={"path": path, "repo_root": str(self.repo_root)},
        )

    def _read_allowed_roots(self) -> tuple[Path, ...]:
        """Return trusted roots that can be read without write permission."""

        codex_home = Path(os.getenv("CODEX_HOME", "~/.codex")).expanduser().resolve()
        return (
            self.repo_root,
            codex_home / "skills",
        )

    def truncate_text(self, text: str, *, max_lines: int, max_bytes: int, tail: bool = False) -> tuple[str, bool]:
        """Truncate text by line and byte ceilings and report truncation flag."""

        max_lines = max(1, max_lines)
        max_bytes = max(1, max_bytes)

        lines = text.splitlines()
        truncated = False
        if len(lines) > max_lines:
            lines = lines[-max_lines:] if tail else lines[:max_lines]
            truncated = True

        while lines and len("\n".join(lines).encode("utf-8")) > max_bytes:
            lines = lines[1:] if tail else lines[:-1]
            truncated = True

        return "\n".join(lines), truncated

    def check_command_policy(self, command: str, *, tool_name: str) -> CommandPolicyDecision:
        """Classify command as allow/deny/review using current policy config."""

        normalized = command.strip().lower()
        if not normalized:
            raise ToolError("command cannot be empty", tool_name=tool_name)

        for fragment in self.config.bash_blocked_fragments:
            if fragment in normalized:
                return CommandPolicyDecision(
                    status="denied",
                    details={"blocked_fragment": fragment},
                )

        _ensure_command_parseable(command=command, tool_name=tool_name)

        unmatched_segments: list[str] = []
        for segment in _split_and_segments(command):
            if not _matches_any_allowed_prefix(
                segment=segment,
                allow_prefixes=_combined_allow_prefixes(self.config),
            ):
                unmatched_segments.append(segment)

        if unmatched_segments:
            return CommandPolicyDecision(
                status="review",
                details={
                    "allow_prefixes": _combined_allow_prefixes(self.config),
                    "unmatched_segments": tuple(unmatched_segments),
                },
            )
        return CommandPolicyDecision(status="allowed", details={})

    def enforce_command_policy(
        self,
        command: str,
        *,
        tool_name: str,
        allow_unlisted: bool = False,
    ) -> None:
        """Validate command policy and optionally allow LLM-reviewed unlisted commands."""

        decision = self.check_command_policy(command, tool_name=tool_name)
        if decision.status == "allowed":
            return
        if decision.status == "review" and allow_unlisted:
            return
        raise ToolError(
            "command is not allowed by policy",
            tool_name=tool_name,
            details=dict(decision.details),
        )

    def run_command(
        self,
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,
    ) -> CommandExecution:
        """Run one command under policy/time/output limits and return structured output."""

        return self.run_command_stream(
            command=command,
            cwd=cwd,
            timeout=timeout,
            tool_name=tool_name,
            allow_unlisted=allow_unlisted,
            on_event=None,
            heartbeat_interval=0.5,
        )

    def run_command_stream(
        self,
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,
        on_event: Callable[[Mapping[str, Any]], None] | None = None,
        heartbeat_interval: float = 0.5,
    ) -> CommandExecution:
        """Run one command and optionally emit realtime execution progress events."""

        self.enforce_command_policy(
            command,
            tool_name=tool_name,
            allow_unlisted=allow_unlisted,
        )

        process = subprocess.Popen(  # noqa: S603
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        if process.stdout is None or process.stderr is None:
            raise ToolError("command stream unavailable", tool_name=tool_name)

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, data="stdout")
        selector.register(process.stderr, selectors.EVENT_READ, data="stderr")

        start_monotonic = time.monotonic()
        deadline = start_monotonic + timeout if timeout is not None else None
        last_heartbeat = start_monotonic
        seq = 0
        timed_out = False
        aborted = False
        merged_parts: list[str] = []

        _emit_command_event(
            on_event,
            {
                "phase": "started",
                "status": "started",
                "elapsed_ms": 0,
            },
        )

        try:
            while True:
                now = time.monotonic()
                if deadline is not None and now >= deadline and process.poll() is None:
                    timed_out = True
                    process.kill()

                wait_timeout = heartbeat_interval
                if deadline is not None:
                    wait_timeout = min(wait_timeout, max(0.0, deadline - now))

                for key, _ in selector.select(timeout=wait_timeout):
                    stream_name = str(key.data)
                    chunk_bytes = os.read(key.fileobj.fileno(), 4096)
                    if not chunk_bytes:
                        selector.unregister(key.fileobj)
                        continue
                    chunk = _decode_stream_bytes(chunk_bytes)
                    merged_parts.append(chunk)
                    seq += 1
                    _emit_command_event(
                        on_event,
                        {
                            "phase": "chunk",
                            "stream": stream_name,
                            "chunk": chunk,
                            "seq": seq,
                        },
                    )

                current = time.monotonic()
                if process.poll() is not None and not selector.get_map():
                    break
                if process.poll() is None and current - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = current
                    _emit_command_event(
                        on_event,
                        {
                            "phase": "running",
                            "status": "running",
                            "elapsed_ms": int((current - start_monotonic) * 1000),
                        },
                    )
        except KeyboardInterrupt:
            aborted = True
            if process.poll() is None:
                process.kill()
        finally:
            selector.close()

        tail_stdout_bytes, tail_stderr_bytes = process.communicate()
        if tail_stdout_bytes:
            tail_stdout = _decode_stream_bytes(tail_stdout_bytes)
            merged_parts.append(tail_stdout)
        if tail_stderr_bytes:
            tail_stderr = _decode_stream_bytes(tail_stderr_bytes)
            merged_parts.append(tail_stderr)

        exit_code = int(process.returncode if process.returncode is not None else process.wait())
        duration_ms = int((time.monotonic() - start_monotonic) * 1000)
        if aborted:
            status_text = "aborted"
        elif timed_out:
            status_text = "timeout"
        elif exit_code == 0:
            status_text = "completed"
        else:
            status_text = "failed"
        _emit_command_event(
            on_event,
            {
                "phase": "exit",
                "status": status_text,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            },
        )

        full_output = "".join(merged_parts)
        tail_output, truncated, byte_limited, start_line, end_line, total_lines, showing_last = _truncate_tail_output(
            full_output,
            max_lines=self.config.bash_max_output_lines,
            max_bytes=self.config.bash_max_output_bytes,
        )
        full_output_path = None
        if truncated:
            full_output_path = self._persist_full_output(content=full_output)
        return CommandExecution(
            exit_code=exit_code,
            text=tail_output,
            truncated=truncated,
            full_output_path=full_output_path,
            timed_out=timed_out,
            aborted=aborted,
            timeout=timeout,
        )

    def _persist_full_output(self, *, content: str) -> str:
        output_dir = self.repo_root / ".agent" / "tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="bash-output-", suffix=".log", dir=output_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        return str(Path(tmp_path))


def _ensure_command_parseable(*, command: str, tool_name: str) -> None:
    try:
        parsed = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ToolError("command parsing failed", tool_name=tool_name) from exc
    if not parsed:
        raise ToolError("command cannot be empty", tool_name=tool_name)


def _split_and_segments(command: str) -> tuple[str, ...]:
    segments = [segment.strip() for segment in command.split("&&")]
    return tuple(segment for segment in segments if segment)


def _combined_allow_prefixes(config: ToolSafetyConfig) -> tuple[str, ...]:
    prefixes = list(config.bash_allowed_prefixes)
    for command_name in config.bash_allowed_commands:
        stripped = str(command_name).strip()
        if stripped:
            prefixes.append(stripped)
    deduped: list[str] = []
    for prefix in prefixes:
        if prefix not in deduped:
            deduped.append(prefix)
    return tuple(deduped)


def _matches_any_allowed_prefix(*, segment: str, allow_prefixes: tuple[str, ...]) -> bool:
    lowered_segment = segment.strip().lower()
    for prefix in allow_prefixes:
        lowered_prefix = prefix.strip().lower()
        if not lowered_prefix:
            continue
        if not lowered_segment.startswith(lowered_prefix):
            continue
        if len(lowered_segment) == len(lowered_prefix):
            return True
        next_char = lowered_segment[len(lowered_prefix)]
        if next_char.isspace() or next_char in "<>|;&()":
            return True
    return False


def _decode_stream_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _emit_command_event(
    callback: Callable[[Mapping[str, Any]], None] | None,
    payload: Mapping[str, Any],
) -> None:
    if callback is None:
        return
    try:
        callback(dict(payload))
    except Exception:
        # Event sinks are observability-only and must not break command execution.
        return


def _truncate_tail_output(
    content: str,
    *,
    max_lines: int,
    max_bytes: int,
) -> tuple[str, bool, bool, int, int, int, bool]:
    lines = content.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        return "", False, False, 0, 0, 0, False

    max_lines = max(1, max_lines)
    max_bytes = max(1, max_bytes)
    start_index = max(0, total_lines - max_lines)
    selected_lines = list(lines[start_index:])
    line_truncated = total_lines > max_lines
    byte_limited = False

    while selected_lines and len("\n".join(selected_lines).encode("utf-8")) > max_bytes and len(selected_lines) > 1:
        selected_lines = selected_lines[1:]
        start_index += 1
        byte_limited = True

    showing_last = False
    if selected_lines and len("\n".join(selected_lines).encode("utf-8")) > max_bytes:
        byte_limited = True
        showing_last = True
        tail_bytes = selected_lines[-1].encode("utf-8")[-max_bytes:]
        selected_lines = [tail_bytes.decode("utf-8", errors="replace")]

    end_index = start_index + len(selected_lines) - 1
    truncated = line_truncated or byte_limited
    return (
        "\n".join(selected_lines),
        truncated,
        byte_limited,
        start_index + 1,
        end_index + 1,
        total_lines,
        showing_last,
    )


