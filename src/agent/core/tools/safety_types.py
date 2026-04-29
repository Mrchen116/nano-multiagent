"""Core-local structural protocols for tool safety dependencies."""

from pathlib import Path
from typing import Any, Mapping, Protocol


class ToolSafetyConfigLike(Protocol):
    """Describe the minimal config contract required by ``ToolContext.create``."""


class BackgroundCommandHandle(Protocol):
    """Handle for a background shell process started via safety layer."""

    pid: int | None
    output_file: Path

    def poll(self) -> int | None:
        """Return exit code if process has finished, otherwise None."""

    def wait(self) -> "CommandExecution":
        """Block until the process exits and return execution result."""

    def terminate_tree(self) -> None:
        """Terminate the process tree (SIGTERM, then SIGKILL)."""


class CommandExecution(Protocol):
    """Normalized result of a shell command execution."""

    exit_code: int
    text: str
    truncated: bool


class ToolSafetyLike(Protocol):
    """Describe the minimal safety surface consumed by tool implementations."""

    repo_root: Path

    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path and enforce write-safe sandbox boundaries."""

    def resolve_read_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path and enforce read-safe sandbox boundaries."""

    def check_command_policy(self, command: str, *, tool_name: str):  # noqa: ANN201
        """Classify command policy before shell execution."""

    def enforce_command_policy(
        self,
        command: str,
        *,
        tool_name: str,
        allow_unlisted: bool = False,
    ):  # noqa: ANN201
        """Enforce command policy and return execution decision."""

    def run_command(
        self,
        command: str,
        *,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,
        env: Mapping[str, str] | None = None,
    ):  # noqa: ANN201
        """Run one shell command under sandbox policy."""

    def start_command_background(
        self,
        command: str,
        *,
        cwd: Path,
        tool_name: str,
        output_file: Path,
        timeout: float | None,
    ) -> BackgroundCommandHandle:
        """Start a shell command in the background and pump output to ``output_file``."""

    def truncate_text(self, text: str, *, max_lines: int, max_bytes: int, tail: bool = False) -> tuple[str, bool]:
        """Truncate tool output according to line and byte ceilings."""


class ToolSafetyFactory(Protocol):
    """Build concrete tool safety/config objects without importing platform paths."""

    def __call__(self, *, repo_root: Path, config: ToolSafetyConfigLike) -> ToolSafetyLike:
        """Return a concrete safety object rooted at ``repo_root``."""


class ToolSafetyConfigFactory(Protocol):
    """Build a default safety config object for ``ToolContext.create``."""

    def __call__(self) -> ToolSafetyConfigLike:
        """Return a default platform-owned safety config instance."""
