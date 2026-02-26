import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from nano_multiagent.core.errors import ToolError


@dataclass(frozen=True, slots=True)
class ToolSafetyConfig:
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
    exit_code: int
    stdout: str
    stderr: str
    truncated: bool


class ToolSafety:
    def __init__(self, *, repo_root: Path, config: ToolSafetyConfig) -> None:
        self.repo_root = repo_root
        self.config = config

    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.repo_root)
        except ValueError as exc:
            raise ToolError(
                "path is outside repo sandbox",
                tool_name=tool_name,
                details={"path": path, "repo_root": str(self.repo_root)},
            ) from exc
        return resolved

    def truncate_text(self, text: str, *, max_lines: int, max_bytes: int, tail: bool = False) -> tuple[str, bool]:
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
        self.enforce_command_policy(command, tool_name=tool_name)
        effective_timeout = timeout if timeout is not None else self.config.bash_default_timeout
        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(
                f"command timed out after {effective_timeout}s",
                tool_name=tool_name,
                details={"timeout": effective_timeout, "timed_out": True},
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
        return CommandExecution(
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            truncated=stdout_truncated or stderr_truncated,
        )
