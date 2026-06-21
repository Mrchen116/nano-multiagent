"""Core-local structural protocols for tool safety dependencies.

After M6 (bugfix-355): BackgroundCommandHandle, CommandExecution, and bash-
specific method signatures removed from ToolSafetyLike. Bash execution now
lives in agent.platform.background_tasks.shell_runner.ShellRunner (the sole bash
engine after bugfix-417-M4 deleted the BashRunner dead path).
"""

from pathlib import Path
from typing import Protocol


class ToolSafetyConfigLike(Protocol):
    """Describe the minimal config contract required by ``ToolContext.create``."""


class ToolSafetyLike(Protocol):
    """Describe the minimal safety surface consumed by tool implementations.

    After M6 (bugfix-355): bash-specific methods (check_command_policy,
    enforce_command_policy, run_command, start_command_background) and the
    read-allowlist method (resolve_read_path) have been removed. Bash policy
    lives in bash_policy.py; execution lives in ShellRunner.
    """

    repo_root: Path

    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path for write/edit tools — normalization only."""

    def normalize_path(self, path: str, *, cwd: Path) -> Path:
        """Pure path normalization: expanduser + cwd + resolve."""

    def is_path_in_workspace(self, resolved: Path) -> bool:
        """Whether the resolved path lies under the repository root."""

    def truncate_text(
        self, text: str, *, max_lines: int, max_bytes: int, tail: bool = False
    ) -> tuple[str, bool]:
        """Truncate tool output according to line and byte ceilings."""


class ToolSafetyFactory(Protocol):
    """Build concrete tool safety/config objects without importing platform paths."""

    def __call__(
        self, *, repo_root: Path, config: ToolSafetyConfigLike
    ) -> ToolSafetyLike:
        """Return a concrete safety object rooted at ``repo_root``."""


class ToolSafetyConfigFactory(Protocol):
    """Build a default safety config object for ``ToolContext.create``."""

    def __call__(self) -> ToolSafetyConfigLike:
        """Return a default platform-owned safety config instance."""
