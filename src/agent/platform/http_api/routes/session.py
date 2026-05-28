"""Session-scoped HTTP handlers covering message, SSE, tools, and compaction."""

from typing import Any, Mapping

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from agent.core.agent.compaction.types import CompactionSettings
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.core.session.entries import SessionEntry, SessionEntryKind
from agent.core.errors import ModelError
from agent.core.hooks.registry import HookRegistry
from agent.core.session.models import Session
from agent.core.types import Message, TurnResult
from agent.platform.hooks.session_usage import get_session_usage_snapshot
from agent.platform.http_api.sse import (
    EventStreamHub,
    StreamEvent,
    SubscriberOverflowError,
    encode_sse_event,
    encode_stream_error,
)
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.registry import ToolRegistry
from agent.core.runs.registry import RunsRegistry
from agent.platform.permissions.broker import PermissionBroker, PermissionResponse

from ..auth import require_bearer_auth
from ..deps import (
    APIError,
    get_agent_runtime,
    get_event_stream_hub,
    get_hook_registry,
    get_permission_broker,
    get_runs_registry,
    get_session_service,
    get_tool_registry,
    get_trace_id,
)

router = APIRouter(
    prefix="/v1/sessions",
    tags=["sessions"],
    dependencies=[Depends(require_bearer_auth)],
)
# Ownership marker: tests assert exported routers come from the platform route module,
# even though the underlying APIRouter class itself lives in FastAPI.
router.__module__ = __name__

_CONTEXT_BUDGET_MAX_TOKENS = CompactionSettings().context_window


class CreateSessionRequest(BaseModel):
    """Payload for creating a new session container."""

    title: str | None = None
    workspace_root: str | None = None
    system_prompt: str | None = None
    skills: list[str] | None = None
    tool_allowlist: list[str] | None = None
    metadata: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    """Canonical session summary returned by session lookup APIs."""

    session_id: str
    status: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    """Paginated session list response."""

    items: list[SessionResponse]
    limit: int
    offset: int
    has_more: bool


class SendMessageRequest(BaseModel):
    """Synchronous message submission payload."""

    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    priority: str = "next"
    # Session workspace root — the stateless kernel needs it to locate the
    # session JSONL on first load.  Senders (PA gateway, CLI) always know it.
    workspace_root: str | None = None
    # Optional run origin — defaults to USER when absent. PA heartbeat runs pass
    # "heartbeat" so auto_mode_gate can short-circuit to unattended_fallback without
    # blocking on a permission request that nobody will answer.
    origin: str | None = None


class SubmitMessageResponse(BaseModel):
    """JSON RPC response for message submit."""

    run_id: str
    anchor_sequence: int
    injected: bool
    status: str


class AppendMessageRequest(BaseModel):
    """Persist one user/assistant message without triggering a model run."""

    role: str = Field(min_length=1)
    content: str = Field(default="")
    message_id: str | None = None
    turn_id: str | None = None
    parts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    # Session workspace root — required for the stateless kernel to locate the
    # session JSONL.  Senders (PA gateway, CLI) always know it.
    workspace_root: str | None = None

    @model_validator(mode="after")
    def validate_role(self) -> "AppendMessageRequest":
        normalized_role = self.role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        self.role = normalized_role
        return self


class AppendMessageResponse(BaseModel):
    """Projection for one persisted append-only session message."""

    session_id: str
    entry_id: str
    kind: str
    created_at: str
    turn_id: str
    role: str
    content: str
    message_id: str | None = None
    parts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolDescriptor(BaseModel):
    """Tool descriptor visible to one authenticated session."""

    name: str
    description: str
    input_schema: dict[str, Any]


class SessionToolsResponse(BaseModel):
    """Response envelope for session tool listing."""

    session_id: str
    tools: list[ToolDescriptor]


class CompactResultResponse(BaseModel):
    """Compaction details when session history was compacted."""

    reason: str
    entry_id: str
    first_kept_event_id: str
    summary: str
    dropped_event_ids: list[str]
    kept_event_ids: list[str]


class CompactSessionResponse(BaseModel):
    """Compaction details when session history was compacted."""

    session_id: str
    compacted: bool
    result: CompactResultResponse | None


class SessionMessageItem(BaseModel):
    """One message in session history."""

    role: str
    content: str
    message_id: str | None = None
    turn_id: str | None = None
    created_at: str | None = None


class SessionMessagesResponse(BaseModel):
    """Paginated session message history."""

    session_id: str
    messages: list[SessionMessageItem]


class ContextBudgetResponse(BaseModel):
    """Session context budget snapshot used by CLI hints."""

    session_id: str
    used_tokens: int
    max_tokens: int
    remaining_tokens: int
    usage_ratio: float


class InterruptSessionResponse(BaseModel):
    """Result of a force-interrupt request against a session."""

    session_id: str
    interrupted: bool
    run_id: str | None = None


class SessionWorkspaceBody(BaseModel):
    """Request body carrying only the session's workspace_root.

    Used by operations on an existing session (fork/compact/interrupt) so the
    stateless kernel can locate the session JSONL. Optional so legacy callers
    and ``data_dir``-backed test stores still work.
    """

    workspace_root: str | None = None


@router.post("", status_code=201, response_model=SessionResponse)
def create_session(
    payload: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Create one session via HTTP boundary."""
    try:
        workspace_root = _parse_workspace_root(payload.workspace_root)
        session = session_service.create_session(
            workspace_root=workspace_root,
            title=payload.title,
            system_prompt=payload.system_prompt,
            skills=tuple(payload.skills) if payload.skills is not None else None,
            tool_allowlist=tuple(payload.tool_allowlist) if payload.tool_allowlist is not None else None,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    return _to_session_response(session)


@router.get("", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace_root: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """List sessions with offset pagination semantics.

    Scoped to the ``workspace_root`` query param — the stateless kernel has no
    cross-workspace session registry.
    """
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    sessions, has_more = session_service.list_sessions(
        limit=limit, offset=offset, workspace_root=ws_root
    )
    return SessionListResponse(
        items=[_to_session_response(session) for session in sessions],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    workspace_root: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Fetch session by id or map missing session to HTTP 404."""
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    session = session_service.get_session(session_id, workspace_root=ws_root)
    if session is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    return _to_session_response(session)


@router.get("/{session_id}/tools", response_model=SessionToolsResponse)
def list_session_tools(
    session_id: str,
    workspace_root: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> SessionToolsResponse:
    """List available tools for one session after existence check."""
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    return SessionToolsResponse(
        session_id=session_id,
        tools=[
            ToolDescriptor(
                name=spec.name,
                description=spec.description,
                input_schema=dict(spec.input_schema),
            )
            for spec in registry.list_specs()
        ],
    )


@router.post("/{session_id}:fork", response_model=SessionResponse)
async def fork_session(
    session_id: str,
    payload: SessionWorkspaceBody = SessionWorkspaceBody(),
    session_service: SessionService = Depends(get_session_service),
    runtime=Depends(get_agent_runtime),
) -> SessionResponse:
    """Fork a session: create a new independent session with copied history."""
    try:
        ws_root = _optional_workspace_root(payload.workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    new_session = await runtime.fork_session(session_id, workspace_root=ws_root)
    return _to_session_response(new_session)


@router.post("/{session_id}:compact", response_model=CompactSessionResponse)
async def compact_session(
    session_id: str,
    payload: SessionWorkspaceBody = SessionWorkspaceBody(),
    session_service: SessionService = Depends(get_session_service),
    runtime=Depends(get_agent_runtime),
) -> CompactSessionResponse:
    """Trigger manual compaction and return compaction metadata when applied."""
    try:
        ws_root = _optional_workspace_root(payload.workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    try:
        result = await runtime.compact(session_id, workspace_root=ws_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc

    if result is None:
        return CompactSessionResponse(session_id=session_id, compacted=False, result=None)

    return CompactSessionResponse(
        session_id=session_id,
        compacted=True,
        result=CompactResultResponse(
            reason=result.reason.value,
            entry_id=result.entry_id,
            first_kept_event_id=result.first_kept_event_id,
            summary=result.summary,
            dropped_event_ids=list(result.dropped_event_ids),
            kept_event_ids=list(result.kept_event_ids),
        ),
    )


@router.get("/{session_id}/context-budget", response_model=ContextBudgetResponse)
def get_context_budget(
    session_id: str,
    workspace_root: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
    runtime=Depends(get_agent_runtime),
    hook_registry: HookRegistry = Depends(get_hook_registry),
) -> ContextBudgetResponse:
    """Return session context usage for user-facing budget hints."""
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    max_tokens = _resolve_context_window(runtime)
    usage_snapshot = get_session_usage_snapshot(registry=hook_registry, session_id=session_id)
    if usage_snapshot is not None:
        used_tokens = min(max(usage_snapshot.last_total_tokens, 0), max_tokens)
    else:
        used_tokens = 0
    remaining_tokens = max(max_tokens - used_tokens, 0)
    usage_ratio = float(used_tokens) / float(max_tokens)
    return ContextBudgetResponse(
        session_id=session_id,
        used_tokens=used_tokens,
        max_tokens=max_tokens,
        remaining_tokens=remaining_tokens,
        usage_ratio=usage_ratio,
    )


@router.post("/{session_id}/interrupt", response_model=InterruptSessionResponse)
def interrupt_session(
    session_id: str,
    payload: SessionWorkspaceBody = SessionWorkspaceBody(),
    session_service: SessionService = Depends(get_session_service),
    runs: RunsRegistry = Depends(get_runs_registry),
) -> InterruptSessionResponse:
    """Force-interrupt the active run for a session."""
    try:
        ws_root = _optional_workspace_root(payload.workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    run_id = runs.interrupt(session_id)
    return InterruptSessionResponse(
        session_id=session_id,
        interrupted=run_id is not None,
        run_id=run_id,
    )


@router.post("/{session_id}/messages:append", response_model=AppendMessageResponse)
def append_message(
    session_id: str,
    payload: AppendMessageRequest,
    session_service: SessionService = Depends(get_session_service),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
) -> AppendMessageResponse:
    """Persist one append-only session message and publish a session event."""

    try:
        ws_root = _optional_workspace_root(payload.workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    existing = session_service.get_session(session_id, workspace_root=ws_root)
    if existing is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    try:
        append_result = session_service.append_message(
            session_id,
            role=payload.role,
            content=payload.content,
            message_id=payload.message_id,
            turn_id=payload.turn_id,
            parts=payload.parts,
            metadata=payload.metadata,
            idempotency_key=payload.idempotency_key,
            workspace_root=ws_root,
        )
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    entry = append_result.entry
    if append_result.created:
        event_hub.publish(
            event=entry.kind.value,
            session_id=session_id,
            data=_session_entry_payload(entry),
        )
    return _to_append_message_response(entry)


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    workspace_root: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
) -> SessionMessagesResponse:
    """List persisted message entries for one session."""
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )
    entries = session_service.manager.list_entries(session_id, workspace_root=ws_root)
    messages: list[SessionMessageItem] = []
    for entry in entries:
        if entry.kind != SessionEntryKind.TURN_APPENDED:
            continue
        data = entry.data
        messages.append(
            SessionMessageItem(
                role=str(data.get("role", "")),
                content=str(data.get("content", "")),
                message_id=data.get("message_id") if isinstance(data.get("message_id"), str) else None,
                turn_id=data.get("turn_id") if isinstance(data.get("turn_id"), str) else None,
                created_at=entry.created_at,
            )
        )
    return SessionMessagesResponse(
        session_id=session_id,
        messages=messages[-limit:] if len(messages) > limit else messages,
    )


@router.post("/{session_id}/messages", response_model=SubmitMessageResponse)
async def submit_message(
    session_id: str,
    payload: SendMessageRequest,
    runs: RunsRegistry = Depends(get_runs_registry),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
    session_service: SessionService = Depends(get_session_service),
    request: Request = None,  # type: ignore[assignment]
) -> SubmitMessageResponse:
    """Submit a message turn and return run handle (JSON RPC, no SSE)."""
    try:
        ws_root = _optional_workspace_root(payload.workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    # priority='now': interrupt active run before starting new one
    if payload.priority == "now":
        runs.interrupt(session_id)

    # priority='next': inject into active run if one exists
    if payload.priority == "next" and runs.get_active_run_id(session_id) is not None:
        anchor = event_hub.current_sequence()
        active_run_id = runs.get_active_run_id(session_id)
        user_text = " ".join(
            part.get("text", "") for part in payload.parts if part.get("type") == "text"
        ).strip() or "[message]"
        injected = runs.inject_pending_message(
            session_id,
            LLMMessage(role="user", content=user_text),
        )
        if injected:
            return SubmitMessageResponse(
                run_id=active_run_id,
                anchor_sequence=anchor,
                injected=True,
                status="injected",
            )

    anchor = event_hub.current_sequence()
    # Resolve origin: caller may pass "heartbeat" for PA background runs so
    # auto_mode_gate can detect unattended context and skip permission requests.
    # Any unrecognised value falls back to USER (safe default).
    _origin_str = (payload.origin or "").strip().lower()
    try:
        run_origin = RunOrigin(_origin_str) if _origin_str else RunOrigin.USER
    except ValueError:
        run_origin = RunOrigin.USER
    try:
        record = runs.submit(
            session_id=session_id,
            parts=payload.parts,
            origin=run_origin,
            trace_id=get_trace_id(request),
            workspace_root=ws_root,
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("session does not exist:"):
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="session_not_found",
                message=message,
                retryable=False,
            ) from exc
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=message,
            retryable=False,
        ) from exc
    return SubmitMessageResponse(
        run_id=record.run_id,
        anchor_sequence=anchor,
        injected=False,
        status=record.status.value,
    )


@router.get("/{session_id}/stream")
async def session_stream(
    session_id: str,
    request: Request,
    workspace_root: str | None = Query(default=None),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
    session_service: SessionService = Depends(get_session_service),
) -> StreamingResponse:
    """Persistent session-scoped SSE stream."""
    try:
        ws_root = _optional_workspace_root(workspace_root)
    except ValueError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request",
            message=str(exc),
            retryable=False,
        ) from exc
    if session_service.get_session(session_id, workspace_root=ws_root) is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=f"session does not exist: {session_id}",
            retryable=False,
        )

    last_event_id = _parse_last_event_id(request.headers)
    if last_event_id is not None and not event_hub.has_sequence(last_event_id):
        async def _err_only():
            yield encode_stream_error(
                session_id=session_id,
                run_id=None,
                code="resume_window_exceeded",
                message="event history pruned beyond Last-Event-ID",
            )
        return StreamingResponse(_err_only(), media_type="text/event-stream")

    after = last_event_id if last_event_id is not None else event_hub.current_sequence()
    return StreamingResponse(
        _session_stream_generator(session_id=session_id, after_sequence=after, event_hub=event_hub),
        media_type="text/event-stream",
    )


def _to_session_response(session: Session) -> SessionResponse:
    """Convert domain session model to HTTP response schema."""
    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
        metadata={
            "workspace_root": str(session.workspace_root),
            **({} if session.system_prompt is None else {"system_prompt": session.system_prompt}),
            **({} if session.skills is None else {"skills": list(session.skills)}),
            **({} if session.tool_allowlist is None else {"tool_allowlist": list(session.tool_allowlist)}),
            **dict(session.metadata),
        },
    )


def _to_append_message_response(entry: SessionEntry) -> AppendMessageResponse:
    """Convert one persisted turn-appended entry into HTTP response shape."""

    return AppendMessageResponse(
        session_id=entry.session_id,
        entry_id=entry.entry_id,
        kind=entry.kind.value,
        created_at=entry.created_at,
        turn_id=str(entry.data.get("turn_id", "")),
        role=str(entry.data.get("role", "")),
        content=str(entry.data.get("content", "")),
        message_id=entry.data.get("message_id") if isinstance(entry.data.get("message_id"), str) else None,
        parts=[dict(part) for part in entry.data.get("parts", []) if isinstance(part, dict)],
        metadata=dict(entry.data.get("metadata", {})) if isinstance(entry.data.get("metadata"), dict) else {},
    )


def _session_entry_payload(entry: SessionEntry) -> dict[str, Any]:
    """Encode one session entry for SSE publication."""

    return {
        "entry_id": entry.entry_id,
        "session_id": entry.session_id,
        "created_at": entry.created_at,
        "kind": entry.kind.value,
        **dict(entry.data),
    }


def _parse_workspace_root(workspace_root: str | None) -> Path:
    """Normalize and validate workspace_root, defaulting to CWD when absent.

    Used by ``create_session`` where a session must be bound to *some* workspace;
    CWD is the documented default for that one path. Operations on an *existing*
    session use ``_optional_workspace_root`` instead — they must not invent a
    CWD-based location, since that is exactly the bugfix-348 bug.
    """
    if workspace_root is None or not workspace_root.strip():
        return Path.cwd()
    candidate = Path(workspace_root.strip()).expanduser()
    if not candidate.is_absolute():
        raise ValueError("workspace_root must be an absolute path or start with ~/")
    return candidate.resolve()


def _optional_workspace_root(workspace_root: str | None) -> Path | None:
    """Normalize an optional workspace_root for operations on an existing session.

    Returns ``None`` when absent (no CWD fallback): the stateless store then
    raises a clear error rather than silently resolving to the process cwd.
    """
    if workspace_root is None or not workspace_root.strip():
        return None
    candidate = Path(workspace_root.strip()).expanduser()
    if not candidate.is_absolute():
        raise ValueError("workspace_root must be an absolute path or start with ~/")
    return candidate.resolve()


def _resolve_context_window(runtime: object) -> int:
    """Resolve user-facing context budget ceiling.

    Notes:
        Context budget tracks the same runtime `context_window` source used by
        compaction policy checks.
    """
    settings = getattr(runtime, "_compaction_settings", None)
    context_window = getattr(settings, "context_window", None)
    if isinstance(context_window, int) and not isinstance(context_window, bool) and context_window > 0:
        return context_window
    return _CONTEXT_BUDGET_MAX_TOKENS


def _parse_last_event_id(headers: Mapping[str, str]) -> int | None:
    """Extract Last-Event-ID from request headers."""
    raw = headers.get("last-event-id")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _session_stream_generator(
    *,
    session_id: str,
    after_sequence: int,
    event_hub: EventStreamHub,
) -> AsyncIterator[str]:
    try:
        async for event in event_hub.stream_session(session_id=session_id, after_sequence=after_sequence):
            yield encode_sse_event(
                sequence_num=event.sequence_num,
                event_id=event.event_id,
                event=event.event,
                data=event.data,
            )
    except SubscriberOverflowError:
        yield encode_stream_error(
            session_id=session_id,
            run_id=None,
            code="subscriber_overflow",
            message="server backlog overflow; reconnect with Last-Event-ID",
        )


# ---------------------------------------------------------------------------
# Permission inbound endpoint (auto_mode_gate ask flow)
# ---------------------------------------------------------------------------

class PermissionDecisionRequest(BaseModel):
    """User decision for a pending permission request.

    Sent by CLI (direct POST) or PA (via Gateway relay) after the user
    chooses a permission option in the picker / IM card.
    """

    decision: str = Field(
        ...,
        description=(
            "Permission decision: 'allow_once' | 'deny' | "
            "'allow_session' | 'allow_always'"
        ),
    )
    request_id: str = Field(default="", description="Echo of the request_id being resolved.")
    reason: str = Field(default="", description="Optional user-supplied reason.")
    rule_update: dict | None = Field(
        default=None,
        description="For 'allow_always': rule to persist in workspace config.",
    )

    @model_validator(mode="after")
    def _validate_decision(self) -> "PermissionDecisionRequest":
        valid = {"allow_once", "deny", "allow_session", "allow_always"}
        if self.decision not in valid:
            raise ValueError(
                f"decision must be one of {sorted(valid)!r}; got {self.decision!r}"
            )
        return self


@router.post("/{session_id}/permissions/{request_id}", status_code=200)
def submit_permission_decision(
    session_id: str,
    request_id: str,
    body: PermissionDecisionRequest,
    broker: PermissionBroker = Depends(get_permission_broker),
) -> dict:
    """Submit a user decision for a pending permission request.

    Resolves the asyncio.Future held by PermissionBroker, unblocking the
    parked auto_mode_gate hook coroutine. Idempotent: resolving an unknown
    or already-resolved request_id returns 404.

    Args:
        session_id: The session owning the pending permission request.
        request_id: The unique identifier of the permission request.
        body: The user's decision (allow_once / deny / allow_session / allow_always).
        broker: PermissionBroker injected from app state.

    Returns:
        JSON ``{"resolved": true, "request_id": ..., "decision": ...}`` on success.

    Raises:
        APIError: 404 when request_id is not pending (unknown or already resolved).
    """
    # Check request is actually pending before resolving
    if not broker.is_pending(request_id):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="permission_request_not_found",
            message=f"permission request not found or already resolved: {request_id}",
            retryable=False,
        )

    response = PermissionResponse(
        decision=body.decision,  # type: ignore[arg-type]
        request_id=request_id,
        reason=body.reason,
        rule_update=body.rule_update,
    )
    broker.resolve(request_id, response)

    return {
        "resolved": True,
        "request_id": request_id,
        "decision": body.decision,
    }
