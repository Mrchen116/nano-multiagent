"""Sandbox and command policy primitives used by file/shell tools."""

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nano_multiagent.core.errors import ToolError


@dataclass(frozen=True, slots=True)
class ToolSafetyConfig:
    """Configure read/bash output limits and executable allow/block policies."""

    read_max_lines: int = 200
    read_max_bytes: int = 64 * 1024
    bash_max_output_lines: int = 200
    bash_max_output_bytes: int = 64 * 1024
    bash_default_timeout: float = 30.0
    bash_allowed_commands: tuple[str, ...] = (
        "bash",
        "cat",
        "echo",
        "false",
        "git",
        "head",
        "ls",
        "pwd",
        "pytest",
        "python",
        "rg",
        "sed",
        "sleep",
        "tail",
        "true",
        "wc",
    )
    bash_blocked_fragments: tuple[str, ...] = (
        ":(){",
        "mkfs",
        "reboot",
        "rm -rf /",
        "shutdown",
    )


@dataclass(frozen=True, slots=True)
class CommandExecution:
    """Capture normalized command execution output after truncation policy."""

    exit_code: int
    stdout: str
    stderr: str
    truncated: bool
    full_output_path: str | None = None


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

    def enforce_command_policy(self, command: str, *, tool_name: str) -> None:
        """Validate a command against deny-list fragments and executable allow-list."""

        normalized = command.strip().lower()
        if not normalized:
            raise ToolError("command cannot be empty", tool_name=tool_name)

        for fragment in self.config.bash_blocked_fragments:
            if fragment in normalized:
                raise ToolError(
                    "command is not allowed by policy",
                    tool_name=tool_name,
                    details={"blocked_fragment": fragment},
                )

        try:
            parts = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ToolError("command parsing failed", tool_name=tool_name) from exc

        if not parts:
            raise ToolError("command cannot be empty", tool_name=tool_name)

        executable = Path(parts[0]).name
        # POLICY TRADE-OFF: allow-list by executable name is intentionally simple and
        # auditable, but still permissive for shell composition handled by callers.
        if executable not in self.config.bash_allowed_commands:
            raise ToolError(
                "command is not allowed by policy",
                tool_name=tool_name,
                details={"executable": executable},
            )

    def run_command(
        self,
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
    ) -> CommandExecution:
        """Run one command under policy/time/output limits and return structured output."""

        self.enforce_command_policy(command, tool_name=tool_name)
        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            timeout_details = timeout if timeout is not None else 0.0
            raise ToolError(
                f"command timed out after {timeout_details}s",
                tool_name=tool_name,
                details={"timeout": timeout_details, "timed_out": True},
            ) from exc

        stdout, stdout_truncated = self.truncate_text(
            completed.stdout,
            max_lines=self.config.bash_max_output_lines,
            max_bytes=self.config.bash_max_output_bytes,
            tail=True,
        )
        stderr, stderr_truncated = self.truncate_text(
            completed.stderr,
            max_lines=self.config.bash_max_output_lines,
            max_bytes=self.config.bash_max_output_bytes,
            tail=True,
        )
        truncated = stdout_truncated or stderr_truncated
        full_output_path = None
        if truncated:
            full_output_path = self._persist_full_output(stdout=completed.stdout, stderr=completed.stderr)
        return CommandExecution(
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            truncated=truncated,
            full_output_path=full_output_path,
        )

    def _persist_full_output(self, *, stdout: str, stderr: str) -> str:
        output_dir = self.repo_root / ".nano_multiagent" / "tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="bash-output-", suffix=".log", dir=output_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(stdout)
            if stderr:
                if stdout and not stdout.endswith("\n"):
                    handle.write("\n")
                handle.write(stderr)
        return str(Path(tmp_path))
