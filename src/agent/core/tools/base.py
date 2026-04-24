"""Shared tool protocol and immutable execution context."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from .safety_types import (
    ToolSafetyConfigFactory,
    ToolSafetyConfigLike,
    ToolSafetyFactory,
    ToolSafetyLike,
)

if TYPE_CHECKING:
    from agent.core.llm.interfaces import LLMClient

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
    max_result_size_chars: int | None = None

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        """Run tool with validated args and context."""

    def serialize_result(self, output: Any, error: str | None = None) -> str | list[dict[str, Any]]:
        """Serialize tool result into LLM-facing content.

        Returns either a plain string (text-only tools) or a list of
        provider-neutral content blocks (multimodal tools like read).
        The kernel loop forwards this directly to mappers without JSON
        round-tripping.

        Args:
            output: Structured output from ``run()`` (success) or None (error).
            error: Error message when ``run()`` raised an exception; None on success.
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
    # Session-scoped file state tracker for deduplication and Read-Before-Write.
    session_file_state: Optional["SessionFileState"] = None
    # Optional LLM client for tools that need on-the-fly model calls (e.g. web_fetch prompt processing).
    llm_client: Optional["LLMClient"] = None

    @classmethod
    def create(
        cls,
        *,
        repo_root: Path,
        cwd: Path | None = None,
        safety_config: ToolSafetyConfigLike | None = None,
        llm_client: Optional["LLMClient"] = None,
    ) -> "ToolContext":
        """Build a context rooted at the resolved repository sandbox."""

        resolved_root = repo_root.expanduser().resolve()
        resolved_cwd = (cwd or resolved_root).expanduser().resolve()
        effective_config = safety_config if safety_config is not None else _build_default_tool_safety_config()
        safety = _require_tool_safety_factory()(repo_root=resolved_root, config=effective_config)
        return cls(repo_root=resolved_root, cwd=resolved_cwd, safety=safety, llm_client=llm_client)

    def with_session(
        self,
        session_id: str | None,
        *,
        tool_call_id: str | None = None,
        safety_overrides: Mapping[str, Any] | None = None,
        execution_event_callback: Callable[[Mapping[str, Any]], None] | None = None,
        session_metadata: Mapping[str, Any] | None = None,
        session_file_state: Optional["SessionFileState"] = None,
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
            session_file_state=session_file_state,
            llm_client=self.llm_client,
        )

    def emit_execution_event(self, payload: Mapping[str, Any]) -> None:
        """Forward one tool execution update to runtime/hook observers when available."""

        callback = self.execution_event_callback
        if callback is None:
            return
        callback(dict(payload))
