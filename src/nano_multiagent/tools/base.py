from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from .safety import ToolSafety, ToolSafetyConfig


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    input_schema: Mapping[str, Any]

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        """Run tool with validated args and context."""


@dataclass(frozen=True, slots=True)
class ToolContext:
    repo_root: Path
    cwd: Path
    safety: ToolSafety
    session_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        repo_root: Path,
        cwd: Path | None = None,
        safety_config: ToolSafetyConfig | None = None,
    ) -> "ToolContext":
        resolved_root = repo_root.expanduser().resolve()
        resolved_cwd = (cwd or resolved_root).expanduser().resolve()
        safety = ToolSafety(repo_root=resolved_root, config=safety_config or ToolSafetyConfig())
        return cls(repo_root=resolved_root, cwd=resolved_cwd, safety=safety)

    def with_session(self, session_id: str | None) -> "ToolContext":
        return ToolContext(
            repo_root=self.repo_root,
            cwd=self.cwd,
            safety=self.safety,
            session_id=session_id,
        )
