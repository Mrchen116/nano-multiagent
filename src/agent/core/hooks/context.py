"""Canonical hook logging facade and per-dispatch context container."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping

from agent.core.observability.logger import log_debug, log_error, log_info, log_warn
from agent.core.observability.tracing import current_trace_id

if TYPE_CHECKING:
    # Avoid circular import at runtime; auto_mode_gate imports from platform.
    # HookContext is pure core — it must not import from platform.
    # PermissionRequest / PermissionResponse types are duck-typed at runtime.
    pass

LogSink = Callable[[str, str, Mapping[str, Any]], None]

# Type alias for the permission requester callable.
# Defined as a broad callable rather than importing platform types to keep
# core independent of platform (core → platform dependency is forbidden).
HookPermissionRequester = Callable[[Any], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class HookModelCall:
    """Model call request shape exposed to hook handlers."""

    session_id: str
    system_prompt: str
    user_prompt: str
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    stop_sequences: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # Caller-level override for provider request body (e.g. disable thinking for gate classifier).
    # Values here take precedence over model metadata extra_request_body in the provider client.
    extra_body: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class HookModelResult:
    """Model call result returned to hook handlers."""

    model: str
    content: str
    raw: Mapping[str, Any] = field(default_factory=dict)


HookModelCaller = Callable[[HookModelCall], HookModelResult]
HookSessionEventPublisher = Callable[[str, Mapping[str, Any]], None]

# Callable signature for the fork_conversation capability injected into background hooks.
# review_prompt: the prompt string sent as first user message to the fork agent.
# tool_allowlist: execution-layer whitelist — only these tool names are allowed to run.
# max_turns: max LLM iterations in the fork side-chain.
# Returns a ForkResult (opaque to core; platform/hooks/builtins interpret it).
ForkConversation = Callable[
    ...,  # (review_prompt: str, *, tool_allowlist: tuple[str,...], max_turns: int) -> Awaitable
    Awaitable[Any],
]


class HookLogger:
    """Emit structured hook logs with optional sink override and base fields."""

    def __init__(
        self,
        sink: LogSink | None = None,
        *,
        base_fields: Mapping[str, Any] | None = None,
    ) -> None:
        self._sink = sink
        self._base_fields = dict(base_fields or {})
        self._logger = logging.getLogger("agent.core.hooks")

    def debug(self, message: str, **fields: Any) -> None:
        """Emit a debug-level hook log entry."""

        self._emit("debug", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        """Emit an info-level hook log entry."""

        self._emit("info", message, fields)

    def warn(self, message: str, **fields: Any) -> None:
        """Emit a warning-level hook log entry."""

        self._emit("warning", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        """Emit an error-level hook log entry."""

        self._emit("error", message, fields)

    def with_fields(self, **fields: Any) -> "HookLogger":
        """Return a logger copy with merged base fields."""

        merged = dict(self._base_fields)
        for key, value in fields.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        return HookLogger(self._sink, base_fields=merged)

    def _emit(self, level: str, message: str, fields: Mapping[str, Any]) -> None:
        merged_fields = dict(self._base_fields)
        merged_fields.update(dict(fields))
        if self._sink is not None:
            self._sink(level, message, merged_fields)
            return
        if level == "debug":
            log_debug(message, **merged_fields)
            return
        if level == "info":
            log_info(message, **merged_fields)
            return
        if level == "warning":
            log_warn(message, **merged_fields)
            return
        if level == "error":
            log_error(message, **merged_fields)
            return
        if merged_fields:
            rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(merged_fields.items()))
            message = f"{message} | {rendered}"
        getattr(self._logger, level)(message)


@dataclass(frozen=True, slots=True)
class HookContext:
    """Carry immutable metadata and logger for a single hook dispatch."""

    session_id: str
    turn_id: str | None = None
    repo_root: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    logger: HookLogger = field(default_factory=HookLogger)
    model_caller: HookModelCaller | None = None
    session_event_publisher: HookSessionEventPublisher | None = None
    # Classifier transcript: tuple of LLM messages (user + assistant tool_use).
    # Populated by AgentLoop per-turn; empty when unavailable (e.g. first turn).
    # Type is tuple[Any, ...] to avoid importing LLMMessage from core.llm here.
    message_history: tuple[Any, ...] = ()
    # Injected by platform layer (PermissionBroker); None in contexts that do
    # not support the ask flow (e.g. CI runs without interactive terminal).
    permission_requester: HookPermissionRequester | None = None
    # fork_conversation is only injected for BACKGROUND hook dispatches.
    # Observe/intercept hooks always see None here.
    # Inside a fork side-chain this is also None to prevent recursive forking (R1).
    fork_conversation: ForkConversation | None = None

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.repo_root is not None:
            object.__setattr__(self, "repo_root", self.repo_root.expanduser().resolve())
        trace_id = self.metadata.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            trace_id = current_trace_id()
        tool_call_id = self.metadata.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            tool_call_id = None
        object.__setattr__(
            self,
            "logger",
            self.logger.with_fields(
                session_id=self.session_id,
                turn_id=self.turn_id,
                tool_call_id=tool_call_id,
                trace_id=trace_id,
            ),
        )

    async def call_model(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: tuple[str, ...] | list[str] = (),
        metadata: Mapping[str, Any] | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> HookModelResult:
        """Call the runtime model with enforced session-id consistency.

        Notes:
            The request session id is always `self.session_id`; callers cannot override it.
        """

        caller = self.model_caller
        if caller is None:
            raise RuntimeError("model caller is unavailable in this hook context")
        result = caller(
            HookModelCall(
                session_id=self.session_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=tuple(stop_sequences),
                metadata=dict(metadata or {}),
                extra_body=dict(extra_body) if extra_body is not None else None,
            )
        )
        if hasattr(result, "__await__"):
            return await result
        return result  # type: ignore[return-value]

    def publish_session_event(
        self,
        *,
        event: str,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Publish one session-scoped event with enforced session consistency."""

        publisher = self.session_event_publisher
        if publisher is None:
            raise RuntimeError("session event publisher is unavailable in this hook context")
        publisher(event, dict(data or {}))

    async def request_permission(self, req: Any) -> Any:
        """Park hook coroutine awaiting a user permission decision.

        Delegates to ``permission_requester`` when injected by the platform
        layer (PermissionBroker). When unavailable (no interactive channel),
        fail-closes: returns a ``PermissionResponse``-compatible object with
        ``decision="deny"`` so the gate never silently passes.

        Args:
            req: ``PermissionRequest`` describing the pending tool call.
                 Type is ``Any`` to avoid importing platform types from core.

        Returns:
            ``PermissionResponse`` (or compatible mapping) with the user's
            decision. Always returns deny when no requester is available.
        """
        requester = self.permission_requester
        if requester is None:
            # Fail-closed: no interactive permission channel → deny.
            # Import here (only reached at runtime when permission requested
            # but no broker is wired) to keep the class definition clean.
            # This import is intentionally deferred — see TYPE_CHECKING guard.
            from agent.platform.permissions.broker import PermissionResponse  # noqa: PLC0415

            return PermissionResponse(
                decision="deny",
                reason="no permission channel (fail-closed)",
            )
        return await requester(req)
