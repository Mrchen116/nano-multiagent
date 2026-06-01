"""Sandbox and path-normalization primitives used by file tools.

After M6 (bugfix-355):
- ToolSafetyConfig retains only read-related budget fields (no bash_* fields).
- ToolSafety retains only path resolution + truncation helpers.
- Bash policy, execution, and subprocess mechanics have been extracted to:
    - agent.platform.tools.builtins.bash_policy  (strategy layer)
    - agent.platform.tools.builtins.bash_runner   (execution layer)
- CommandPolicyDecision has been moved to bash_policy; this module keeps
  a shim export so existing callers still import without breaking.
"""

from dataclasses import dataclass
from pathlib import Path


from .constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES


@dataclass(frozen=True, slots=True)
class ToolSafetyConfig:
    """Configure read output limits (I/O budget for file tools).

    After M6: bash execution limits (bash_max_output_lines, bash_max_output_bytes,
    bash_default_timeout) and command policy constants (bash_allowed_prefixes,
    bash_blocked_commands, etc.) have been removed. Those now live in
    BashRunnerConfig and bash_policy.BASH_* constants respectively.
    """

    read_max_lines: int = DEFAULT_MAX_LINES
    read_max_bytes: int = DEFAULT_MAX_BYTES


def load_tool_safety_config(
    *, repo_root: Path, default: ToolSafetyConfig | None = None
) -> ToolSafetyConfig:
    """Load optional `.nano/policy.toml` overrides for file-tool safety.

    After M6: bash policy overrides are handled by bash_policy.load_bash_policy_overrides.
    This function only loads read budget overrides (currently no TOML key for those,
    so it always returns the default/base).
    """
    return default or ToolSafetyConfig()


@dataclass(frozen=True, slots=True)
class CommandExecution:
    """Capture normalized command execution output after truncation policy."""

    exit_code: int
    text: str
    truncated: bool
    full_output_path: str | None = None
    output_file_path: str | None = None  # original output file path (file mode)
    file_size: int = 0  # output file size in bytes
    timed_out: bool = False
    aborted: bool = False
    timeout: float | None = None


class ToolSafety:
    """Enforce filesystem guardrails for tool execution.

    After M6: bash-specific methods (check_command_policy, enforce_command_policy,
    run_command_stream, run_command, start_command_background) have been removed.
    Those now live in bash_policy.py and bash_runner.py.

    Remaining surface:
    - resolve_path         write/edit tools path resolution (sandbox normalization)
    - normalize_path       pure normalization — expanduser + cwd + resolve
    - is_path_in_workspace test if a path is inside the workspace root
    - truncate_text        output truncation helper
    """

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

    def truncate_text(
        self, text: str, *, max_lines: int, max_bytes: int, tail: bool = False
    ) -> tuple[str, bool]:
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


# ---------------------------------------------------------------------------
# Shim: CommandPolicyDecision exported from this module for backward compat.
# New code should import from agent.platform.tools.builtins.bash_policy.
# ---------------------------------------------------------------------------

from agent.platform.tools.builtins.bash_policy import (
    CommandPolicyDecision as CommandPolicyDecision,
)  # noqa: E402, F401
