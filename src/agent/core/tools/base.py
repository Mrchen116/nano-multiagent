"""Shared tool protocol and immutable execution context."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .file_state_cache import FileStateCache
from .safety_types import (
    ToolSafetyConfigFactory,
    ToolSafetyConfigLike,
    ToolSafetyFactory,
    ToolSafetyLike,
)

_TOOL_SAFETY_FACTORY: ToolSafetyFactory | None = None
_TOOL_SAFETY_CONFIG_FACTORY: ToolSafetyConfigFactory | None = None


def set_tool_safety_factory(factory: ToolSafetyFactory) -> None:
    """Register the platform-owned tool safety constructor for ToolContext."""

    global _TOOL_SAFETY_FACTORY
    _TOOL_SAFETY_FACTORY = factory


def set_tool_safety_config_factory(factory: ToolSafetyConfigFactory) -> None:
    """Register the platform-owned default safety config constructor."""

    global _TOOL_SAFETY_CONFIG_FACTORY
    _TOOL_SAFETY_CONFIG_FACTORY = factory


def _require_tool_safety_factory() -> ToolSafetyFactory:
    factory = _TOOL_SAFETY_FACTORY
    if factory is None:
        raise RuntimeError("tool safety factory is not configured")
    return factory


def _build_default_tool_safety_config() -> ToolSafetyConfigLike:
    factory = _TOOL_SAFETY_CONFIG_FACTORY
    if factory is None:
        raise RuntimeError("tool safety config factory is not configured")
    return factory()


@runtime_checkable
class Tool(Protocol):
    """Describe the public contract every tool implementation must satisfy."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        """Run tool with validated args and context."""

    def serialize_result(self, output: Any) -> str:
        """Serialize this tool's structured output into LLM-facing tool_message content.

        It is each tool's own responsibility to decide how its business-level result
        is presented to the model (e.g. plain text, JSON, or a specialized stub).
        """
        ...


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Carry sandbox state used by all tool executions within one request."""

    repo_root: Path
    cwd: Path
    safety: ToolSafetyLike
    session_id: str | None = None
    tool_call_id: str | None = None
    safety_overrides: Mapping[str, Any] = field(default_factory=dict)
    execution_event_callback: Callable[[Mapping[str, Any]], None] | None = None
    # Per-session metadata forwarded from the kernel session so product tools
    # (e.g. send_message) can read runtime-injected fields such as
    # ``gateway_dispatch_url`` without requiring a separate registry lookup.
    session_metadata: Mapping[str, Any] = field(default_factory=dict)
    # Session-scoped read-file state cache for mtime-based deduplication.
    read_file_state: FileStateCache | None = None

    @classmethod
    def create(
        cls,
        *,
        repo_root: Path,
        cwd: Path | None = None,
        safety_config: ToolSafetyConfigLike | None = None,
    ) -> "ToolContext":
        """Build a context rooted at the resolved repository sandbox."""

        resolved_root = repo_root.expanduser().resolve()
        resolved_cwd = (cwd or resolved_root).expanduser().resolve()
        effective_config = safety_config if safety_config is not None else _build_default_tool_safety_config()
        safety = _require_tool_safety_factory()(repo_root=resolved_root, config=effective_config)
        return cls(repo_root=resolved_root, cwd=resolved_cwd, safety=safety)

    def with_session(
        self,
        session_id: str | None,
        *,
        tool_call_id: str | None = None,
        safety_overrides: Mapping[str, Any] | None = None,
        execution_event_callback: Callable[[Mapping[str, Any]], None] | None = None,
        session_metadata: Mapping[str, Any] | None = None,
        read_file_state: FileStateCache | None = None,
    ) -> "ToolContext":
        """Clone context with session/call metadata and per-call safety overrides."""

        return ToolContext(
            repo_root=self.repo_root,
            cwd=self.cwd,
            safety=self.safety,
            session_id=session_id,
            tool_call_id=tool_call_id,
            safety_overrides=dict(safety_overrides or {}),
            execution_event_callback=execution_event_callback,
            session_metadata=dict(session_metadata) if session_metadata is not None else dict(self.session_metadata),
            read_file_state=read_file_state,
        )

    def emit_execution_event(self, payload: Mapping[str, Any]) -> None:
        """Forward one tool execution update to runtime/hook observers when available."""

        callback = self.execution_event_callback
        if callback is None:
            return
        callback(dict(payload))
