"""Sandbox and command policy primitives used by file/shell tools."""

import os
import selectors
import shlex
import subprocess
import tempfile
import threading
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
    # Hard-deny — absolute, classifier cannot override.
    # Split into two lists mirroring CC bashSecurity.ts's ZSH_DANGEROUS_COMMANDS
    # Set (token match) vs structural-pattern checks (regex/AST):
    #
    # ``bash_blocked_commands`` matches the *base command* (first token of each
    # ``&&``-split segment, after stripping leading ``VAR=value`` env prefixes).
    # ``bash_blocked_fragments`` keeps the legacy substring match, reserved for
    # syntactic constructs that have no base command (e.g. fork bombs).
    #
    # ``rm`` is intentionally NOT in either list — workspace ``rm -rf /tmp/...``
    # falls under CC yoloClassifier's "Irreversible Local Destruction"
    # category (BLOCK ALWAYS but surface via ask card so the user can confirm).
    # Routing it through the classifier preserves the Auto Mode design intent.
    #
    # Deviation from CC: we keep ``reboot``/``shutdown``/``halt``/``poweroff``/
    # ``mkfs`` in the token blocklist because development agents have zero
    # legitimate reason to invoke them; short-circuiting saves a classifier
    # LLM round-trip. The zsh-module entries below mirror CC's
    # ZSH_DANGEROUS_COMMANDS verbatim (defense-in-depth against ``zmodload``-
    # gated bypasses of binary-name checks).
    bash_blocked_commands: tuple[str, ...] = (
        # System-level destruction — narrow deviation from CC: CC routes these
        # through the classifier; we hard-deny because a dev agent has no
        # legitimate use case for them.
        "mkfs",
        "reboot",
        "shutdown",
        "halt",
        "poweroff",
        # zsh eval / module gateway (mirror CC ZSH_DANGEROUS_COMMANDS).
        "zmodload",
        "emulate",
        # zsh network / pty attack vectors (zsh/net/tcp, zsh/net/socket, zsh/zpty).
        "ztcp",
        "zsocket",
        "zpty",
        # zsh/system — fine-grained fd access bypassing binary checks.
        "sysopen",
        "sysread",
        "syswrite",
        "sysseek",
        # zsh/files — builtin rm/mv/ln/chmod that bypass binary checks.
        "zf_rm",
        "zf_mv",
        "zf_ln",
        "zf_chmod",
        "zf_chown",
        "zf_mkdir",
        "zf_rmdir",
        "zf_chgrp",
        # zsh/mapfile — implicit file I/O via associative array assignment.
        "mapfile",
    )
    # Structural-syntax fragments (substring match). Reserved for shell
    # constructs without a base command — e.g. the fork bomb function literal
    # ``:(){`` which is a function definition, not an executable. AST-based
    # structural checks (CC's DANGEROUS_PATTERNS family) are out of scope here
    # and tracked separately.
    bash_blocked_fragments: tuple[str, ...] = (
        ":(){",
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
    blocked_commands = _read_optional_string_tuple(bash_policy.get("deny_commands"))

    return ToolSafetyConfig(
        read_max_lines=base.read_max_lines,
        read_max_bytes=base.read_max_bytes,
        bash_max_output_lines=base.bash_max_output_lines,
        bash_max_output_bytes=base.bash_max_output_bytes,
        bash_default_timeout=base.bash_default_timeout,
        bash_allowed_prefixes=allowed_prefixes or base.bash_allowed_prefixes,
        bash_allowed_commands=base.bash_allowed_commands,
        bash_blocked_commands=blocked_commands or base.bash_blocked_commands,
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
    output_file_path: str | None = None  # 新增：原始输出文件路径（文件模式）
    file_size: int = 0  # 新增：输出文件大小
    timed_out: bool = False
    aborted: bool = False
    timeout: float | None = None


class _BackgroundCommandHandle:
    """Handle for a background shell process."""

    def __init__(
        self,
        process: subprocess.Popen,
        *,
        output_file: Path,
        timeout: float | None,
    ) -> None:
        self._process = process
        self.output_file = output_file
        self.pid = process.pid
        self._timeout = timeout

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self) -> CommandExecution:
        try:
            exit_code = self._process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            self.terminate_tree()
            try:
                exit_code = self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                exit_code = -9
            text = self._read_output()
            return CommandExecution(
                exit_code=exit_code,
                text=text,
                truncated=False,
                timed_out=True,
            )

        text = self._read_output()
        return CommandExecution(
            exit_code=exit_code,
            text=text,
            truncated=False,
        )

    def terminate_tree(self) -> None:
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        except Exception:
            pass

    def _read_output(self) -> str:
        try:
            if self.output_file.exists():
                return self.output_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return ""


class ToolSafety:
    """Enforce filesystem and shell guardrails for tool execution."""

    def __init__(self, *, repo_root: Path, config: ToolSafetyConfig) -> None:
        self.repo_root = repo_root
        self.config = config

    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path for write/edit tools — normalization only.

        After refactor-353 the workspace boundary check moved into the
        ``auto_mode_gate`` hook so that ``dangerously-skip-permissions`` can
        actually bypass it and so that ``auto`` mode can route out-of-workspace
        writes through the classifier / ask flow instead of hard-erroring.

        Callers (write/edit/multi_edit tools) MUST be wired through the
        hook dispatch path; the contract test
        ``tests/contract/test_file_tools_go_through_hooks.py`` enforces this.
        """

        return self.normalize_path(path, cwd=cwd)

    def normalize_path(self, path: str, *, cwd: Path) -> Path:
        """Pure path normalization: expanduser + cwd + resolve (symlinks/dots).

        Always-on input hygiene — independent of any permission mode. Used by
        both write/edit tools (post-hook authorization) and read tools (which
        additionally enforce the read-allowlist boundary).
        """

        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        return candidate.resolve()

    def is_path_in_workspace(self, resolved: Path) -> bool:
        """Whether the resolved path lies under the repository root.

        TODO(bugfix-355): After write/edit tools fully migrate to tool-level
        check_permissions, this method is only used by test code. Remove when
        migration is complete and tests updated.
        """

        try:
            resolved.relative_to(self.repo_root)
            return True
        except ValueError:
            return False

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

        # Per-segment base-command denylist. Token-level match (mirrors CC's
        # ZSH_DANGEROUS_COMMANDS Set semantics) so we don't false-positive on
        # substrings like ``mkfsd-helper`` or ``reboot-message.txt``.
        blocked_command_set = {cmd.lower() for cmd in self.config.bash_blocked_commands}
        for segment in _split_and_segments(command):
            base_cmd = _extract_base_command(segment)
            if base_cmd and base_cmd in blocked_command_set:
                return CommandPolicyDecision(
                    status="denied",
                    details={"blocked_command": base_cmd, "segment": segment},
                )

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

        # 创建临时输出文件（文件模式）
        output_dir = self.repo_root / ".agent" / "tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="bash-stdout-", suffix=".log", dir=output_dir)
        os.close(tmp_fd)

        MAX_FILE_BYTES = 1 * 1024 * 1024  # 1MB 硬上限

        process = subprocess.Popen(  # noqa: S603
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
        )
        if process.stdout is None:
            raise ToolError("command stream unavailable", tool_name=tool_name)

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, data="stdout")

        start_monotonic = time.monotonic()
        deadline = start_monotonic + timeout if timeout is not None else None
        last_heartbeat = start_monotonic
        seq = 0
        timed_out = False
        aborted = False
        bytes_written = 0
        was_limited = False

        _emit_command_event(
            on_event,
            {
                "phase": "started",
                "status": "started",
                "elapsed_ms": 0,
            },
        )

        with open(tmp_path, "w", encoding="utf-8") as out_f:
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
                        chunk_bytes = os.read(key.fileobj.fileno(), 4096)
                        if not chunk_bytes:
                            selector.unregister(key.fileobj)
                            continue
                        chunk = _decode_stream_bytes(chunk_bytes)

                        # 实时写入文件，1MB 硬上限
                        if bytes_written < MAX_FILE_BYTES:
                            out_f.write(chunk)
                            out_f.flush()
                            bytes_written += len(chunk.encode("utf-8"))
                        else:
                            was_limited = True

                        seq += 1
                        _emit_command_event(
                            on_event,
                            {
                                "phase": "chunk",
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

            # 排空剩余 stdout
            remaining_stdout = process.stdout.read()
            if remaining_stdout:
                chunk = _decode_stream_bytes(remaining_stdout)
                if bytes_written < MAX_FILE_BYTES:
                    out_f.write(chunk)
                    out_f.flush()
                    bytes_written += len(chunk.encode("utf-8"))
                else:
                    was_limited = True

            process.wait()

        exit_code = int(process.returncode if process.returncode is not None else 0)
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

        file_size = os.path.getsize(tmp_path)
        return CommandExecution(
            exit_code=exit_code,
            text="",
            truncated=was_limited,
            output_file_path=tmp_path,
            file_size=file_size,
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

    def start_command_background(
        self,
        command: str,
        *,
        cwd: Path,
        tool_name: str,
        output_file: Path,
        timeout: float | None,
    ) -> _BackgroundCommandHandle:
        """Start a shell command in the background and pump output to ``output_file``."""

        self.enforce_command_policy(
            command,
            tool_name=tool_name,
            allow_unlisted=False,
        )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )

        def _pump(stream: Any, label: str) -> None:
            buffer = ""
            try:
                while True:
                    chunk_bytes = stream.read(4096)
                    if not chunk_bytes:
                        if buffer:
                            with output_file.open("a", encoding="utf-8") as f:
                                prefix = "[stderr] " if label == "stderr" else ""
                                f.write(prefix + buffer)
                        break
                    buffer += chunk_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        with output_file.open("a", encoding="utf-8") as f:
                            prefix = "[stderr] " if label == "stderr" else ""
                            f.write(prefix + line + "\n")
            except Exception:
                pass

        threading.Thread(target=_pump, args=(process.stdout, "stdout"), daemon=True).start()
        threading.Thread(target=_pump, args=(process.stderr, "stderr"), daemon=True).start()

        return _BackgroundCommandHandle(process, output_file=output_file, timeout=timeout)


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


def _extract_base_command(segment: str) -> str:
    """Return the lowercased base command of a segment after stripping ``VAR=val`` prefixes.

    ``VAR=val cmd args`` → ``cmd``;  ``VAR=val OTHER=foo cmd args`` → ``cmd``.
    Mirrors how shells resolve the executable token (bash ignores leading
    name=value assignments). Returns ``""`` when the segment is empty or
    parses to only assignments.
    """

    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        # Fall back to whitespace split — caller still gets a best-effort token
        # so a malformed segment can still hit the denylist if its first word
        # is a blocked command name.
        tokens = segment.split()
    for token in tokens:
        # Skip ``NAME=value`` assignments — bash treats these as env vars, not
        # the executable. Only strip when the equals sign is preceded by a
        # valid identifier (avoids treating ``--foo=bar`` flag-style args here,
        # though such tokens shouldn't appear before the base command anyway).
        if "=" in token:
            head, _, _ = token.partition("=")
            if head and (head[0].isalpha() or head[0] == "_") and all(
                ch.isalnum() or ch == "_" for ch in head
            ):
                continue
        return token.lower()
    return ""


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


