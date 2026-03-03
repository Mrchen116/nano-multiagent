"""Shared tool protocol and immutable execution context."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from .safety import ToolSafety, ToolSafetyConfig


@runtime_checkable
class Tool(Protocol):
    """Describe the public contract every tool implementation must satisfy."""

    name: str
    description: str
    input_schema: Mapping[str, Any]

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        """Run tool with validated args and context."""


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Carry sandbox state used by all tool executions within one request."""

    repo_root: Path
    cwd: Path
    safety: ToolSafety
    session_id: str | None = None
    tool_call_id: str | None = None
    safety_overrides: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        repo_root: Path,
        cwd: Path | None = None,
        safety_config: ToolSafetyConfig | None = None,
    ) -> "ToolContext":
        """Build a context rooted at the resolved repository sandbox."""

        resolved_root = repo_root.expanduser().resolve()
        resolved_cwd = (cwd or resolved_root).expanduser().resolve()
        safety = ToolSafety(repo_root=resolved_root, config=safety_config or ToolSafetyConfig())
        return cls(repo_root=resolved_root, cwd=resolved_cwd, safety=safety)

    def with_session(
        self,
        session_id: str | None,
        *,
        tool_call_id: str | None = None,
        safety_overrides: Mapping[str, Any] | None = None,
    ) -> "ToolContext":
        """Clone context with session/call metadata and per-call safety overrides."""

        return ToolContext(
            repo_root=self.repo_root,
            cwd=self.cwd,
            safety=self.safety,
            session_id=session_id,
            tool_call_id=tool_call_id,
            safety_overrides=dict(safety_overrides or {}),
        )
