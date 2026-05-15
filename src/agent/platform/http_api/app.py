"""FastAPI application factory with shared middleware and error mapping."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent import __version__
from agent.core.agent.runtime import AgentRuntime
from agent.core.ids import make_event_id
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.observability.exporters.console import ConsoleTracer
from agent.core.observability.logger import log_error
from agent.core.observability.tracing import bind_correlation, set_tracer
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.hooks.session_events import set_session_event_publisher_factory
from agent.platform.http_api.sse import EventStreamHub
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.persistence.session.base import SessionStore
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.loader import build_tool_registry
from agent.platform.tools.registry import ToolRegistry
from agent.core.runs.registry import RunsRegistry

if TYPE_CHECKING:
    from agent.products.base import ProductProfile

from .deps import APIError, get_trace_id
from .routes.event import router as event_router
from .routes.global_routes import router as global_router
from .routes.hook import router as hook_router
from .routes.run import router as run_router
from .routes.session import router as session_router
from .routes.tool import router as tool_router


def create_app(
    *,
    session_store: SessionStore | None = None,
    runtime: AgentRuntime | None = None,
    tool_registry: ToolRegistry | None = None,
    hook_registry: HookRegistry | None = None,
    repo_root: Path | None = None,
    product_profile: "ProductProfile | None" = None,
) -> FastAPI:
    """Create and wire the HTTP API application.

    Args:
        session_store: Optional custom session storage backend.
        runtime: Optional prebuilt runtime instance; when omitted runtime is created.
        tool_registry: Optional prebuilt tool registry.
        hook_registry: Optional prebuilt hook registry.
        repo_root: Repository root used by hooks/tool loader.
        product_profile: Optional product profile; when supplied, the app uses
            bootstrap-resolved registries instead of ad-hoc defaults. Explicit
            ``tool_registry``/``hook_registry`` args still override the profile
            when both are provided (explicit > profile > platform defaults).

    Returns:
        Configured FastAPI app with all route groups and middleware attached.

    Notes:
        CLI/SDK must call this runtime through HTTP handlers only; no direct
        runtime imports are required at clients.
    """
    app = FastAPI(title="nano-multiagent", version=__version__)

    # Wire console tracer when threshold env is set (zero-overhead NoOpTracer by default).
    _trace_threshold = os.getenv("NANO_MULTIAGENT_TRACE_CONSOLE_THRESHOLD_MS")
    if _trace_threshold is not None:
        try:
            set_tracer(ConsoleTracer(threshold_ms=float(_trace_threshold)))
        except ValueError:
            set_tracer(ConsoleTracer(threshold_ms=100.0))
    elif os.getenv("NANO_MULTIAGENT_TRACE_CONSOLE"):
        set_tracer(ConsoleTracer(threshold_ms=100.0))

    resolved_repo_root = (
        repo_root or Path(os.getenv("NANO_MULTIAGENT_REPO_ROOT", os.getcwd()))
    ).expanduser().resolve()

    # If a product profile was supplied, bootstrap it to get resolved defaults.
    # Explicit registry args (tool_registry / hook_registry) take precedence
    # over profile-resolved ones, matching the principle of "explicit > profile > defaults".
    resolved_system_prompt: str | None = None
    resolved_config_resolver = None
    resolved_default_tool_ids: list[str] | None = None
    resolved_default_metadata: dict | None = None
    if product_profile is not None:
        from agent.platform.bootstrap import bootstrap_product

        resolved_product = bootstrap_product(
            profile=product_profile,
            repo_root=resolved_repo_root,
        )
        resolved_config_resolver = resolved_product.config_resolver
        if tool_registry is None:
            tool_registry = resolved_product.tool_registry
        if hook_registry is None:
            hook_registry = resolved_product.hook_registry
        if session_store is None and resolved_product.session_store is not None:
            session_store = resolved_product.session_store
        # Inject the product-specific system prompt into the runtime.
        # Empty string means "no prompt declared"; keep None so the runtime
        # uses its own empty-string default rather than setting empty explicitly.
        if resolved_product.resolved_system_prompt:
            resolved_system_prompt = resolved_product.resolved_system_prompt
        # Thread default_tool_ids so the runtime can gate tool exposure per session.
        resolved_default_tool_ids = resolved_product.default_tool_ids
        # Thread default_session_metadata so per-session metadata (e.g.
        # self_evolution config from workspace config.yaml) inherits the
        # product-level defaults resolved at bootstrap; without this the
        # bootstrap field is dead and self-evolution falls back to hard-coded
        # defaults regardless of user config.
        resolved_default_metadata = resolved_product.default_session_metadata
    session_service = SessionService(
        store=session_store,
        profile=product_profile,
        default_session_metadata=resolved_default_metadata,
    )
    app.state.session_service = session_service
    if runtime is None:
        active_hook_registry = hook_registry or build_hook_registry(
            repo_root=resolved_repo_root,
            config_resolver=resolved_config_resolver,
        )
        active_hook_runner = HookRunner(registry=active_hook_registry)
        runtime_kwargs: dict = {}
        if resolved_system_prompt is not None:
            runtime_kwargs["system_prompt"] = resolved_system_prompt
        if resolved_config_resolver is not None:
            runtime_kwargs["config_resolver"] = resolved_config_resolver
        if resolved_default_tool_ids is not None:
            runtime_kwargs["default_tool_ids"] = resolved_default_tool_ids
        active_runtime = AgentRuntime(
            session_manager=session_service.manager,
            hook_runner=active_hook_runner,
            repo_root=resolved_repo_root,
            **runtime_kwargs,
        )
    else:
        active_runtime = runtime
        runtime_hook_registry = getattr(active_runtime, "hook_registry", None)
        runtime_hook_runner = getattr(active_runtime, "hook_runner", None)
        runtime_config_resolver = getattr(active_runtime, "config_resolver", None) or resolved_config_resolver
        active_hook_registry = hook_registry or runtime_hook_registry or build_hook_registry(
            repo_root=resolved_repo_root,
            config_resolver=runtime_config_resolver,
        )
        active_hook_runner = runtime_hook_runner or HookRunner(registry=active_hook_registry)

    app.state.agent_runtime = active_runtime
    app.state.hook_registry = active_hook_registry
    app.state.hook_runner = active_hook_runner
    app.state.event_stream_hub = EventStreamHub()
    set_session_event_publisher_factory(
        registry=active_hook_registry,
        factory=_build_session_event_publisher_factory(event_hub=app.state.event_stream_hub),
    )
    app.state.runs_registry = RunsRegistry(
        runtime=active_runtime,
        session_manager=session_service.manager,
        event_hub=app.state.event_stream_hub,
        hook_runner=active_hook_runner,
    )

    # Wire background task infrastructure
    app.state.background_task_wiring = wire_background_tasks(
        workspace_root=resolved_repo_root,
        runtime=active_runtime,
        runs_registry=app.state.runs_registry,
    )

    active_config_resolver = getattr(active_runtime, "config_resolver", None) or resolved_config_resolver
    app.state.tool_registry = tool_registry or build_tool_registry(
        repo_root=resolved_repo_root,
        hook_runner=active_hook_runner,
        runtime=active_runtime,
        config_resolver=active_config_resolver,
        llm_client=getattr(active_runtime, "_llm_client", None),
        wiring=app.state.background_task_wiring,
    )
    _bind_runtime_to_tool_registry(
        tool_registry=app.state.tool_registry,
        runtime=active_runtime,
        hook_runner=active_hook_runner,
        wiring=app.state.background_task_wiring,
    )
    bind_tool_registry = getattr(active_runtime, "bind_tool_registry", None)
    if callable(bind_tool_registry):
        bind_tool_registry(app.state.tool_registry)
    @app.middleware("http")
    async def trace_middleware(request: Request, call_next: Any):  # type: ignore[valid-type]
        """Bind/propagate `trace_id` on every HTTP request/response."""
        incoming_trace_id = request.headers.get("X-Request-Id", "").strip()
        request.state.trace_id = incoming_trace_id or make_event_id()
        with bind_correlation(trace_id=request.state.trace_id):
            response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.trace_id
        return response

    @app.on_event("shutdown")
    async def emit_session_shutdown_hooks() -> None:
        """Dispatch `session_shutdown` observe hooks before process exits."""
        app.state.runs_registry.shutdown()
        await _dispatch_session_shutdown(
            session_service=session_service,
            hook_runner=active_hook_runner,
            repo_root=resolved_repo_root,
        )

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        """Map internal APIError into stable JSON envelope."""
        trace_id = get_trace_id(request)
        log_error(
            "api_error",
            code=exc.code,
            status_code=exc.status_code,
            trace_id=trace_id,
        )
        return _error_response(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            status_code=exc.status_code,
            trace_id=trace_id,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        """Normalize framework HTTPException into API error contract."""
        trace_id = get_trace_id(request)
        # Keep coarse error codes for client-side retry/auth routing.
        code = "http_error"
        if exc.status_code == 401:
            code = "unauthorized"
        elif exc.status_code == 404:
            code = "not_found"
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        log_error(
            "http_error",
            code=code,
            status_code=exc.status_code,
            trace_id=trace_id,
        )
        return _error_response(
            code=code,
            message=detail,
            retryable=False,
            status_code=exc.status_code,
            trace_id=trace_id,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Map request-schema violations to `invalid_request`."""
        trace_id = get_trace_id(request)
        log_error(
            "request_validation_error",
            code="invalid_request",
            status_code=422,
            trace_id=trace_id,
        )
        return _error_response(
            code="invalid_request",
            message=str(exc).replace("\n", "; "),
            retryable=False,
            status_code=422,
            trace_id=trace_id,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Fail closed for unknown exceptions while keeping traceability."""
        trace_id = get_trace_id(request)
        log_error(
            "unexpected_error",
            code="internal_error",
            status_code=500,
            trace_id=trace_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return _error_response(
            code="internal_error",
            message="internal server error",
            retryable=False,
            status_code=500,
            trace_id=trace_id,
        )

    app.include_router(global_router)
    app.include_router(event_router)
    app.include_router(hook_router)
    app.include_router(session_router)
    app.include_router(run_router)
    app.include_router(tool_router)
    return app


def _error_response(
    *,
    code: str,
    message: str,
    retryable: bool,
    status_code: int,
    trace_id: str,
) -> JSONResponse:
    """Build canonical error response payload shared by all handlers."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "trace_id": trace_id,
            }
        },
    )


def _bind_runtime_to_tool_registry(
    *,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    hook_runner: HookRunner | None,
    wiring: Any | None = None,
) -> None:
    """Backfill runtime/hook wiring onto pre-bootstrapped tool registries."""
    setattr(tool_registry, "_hook_runner", hook_runner)
    tools = getattr(tool_registry, "_tools", {})
    for tool_name in ("agent", "bash", "task_stop"):
        tool = tools.get(tool_name)
        bind_runtime = getattr(tool, "bind_runtime", None)
        if callable(bind_runtime):
            bind_runtime(runtime)
        bind_wiring = getattr(tool, "bind_wiring", None)
        if callable(bind_wiring):
            bind_wiring(wiring)



def _build_session_event_publisher_factory(
    *,
    event_hub: EventStreamHub,
):
    """Build session-bound event publisher factory for hook contexts."""

    def _factory(session_id: str):
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            return None

        def _publish(event: str, data: dict[str, object]) -> None:
            if not isinstance(event, str) or not event.strip():
                return
            payload = dict(data)
            payload["session_id"] = normalized_session_id
            event_hub.publish(
                event=event,
                session_id=normalized_session_id,
                data=payload,
            )

        return _publish

    return _factory


app = create_app()


async def _dispatch_session_shutdown(
    *,
    session_service: SessionService,
    hook_runner: HookRunner | None,
    repo_root: Path,
) -> None:
    """Broadcast shutdown observe hooks for all sessions in paged batches."""
    if hook_runner is None:
        return

    offset = 0
    limit = 100
    while True:
        sessions, has_more = session_service.list_sessions(limit=limit, offset=offset)
        for session in sessions:
            hook_ctx = HookContext(session_id=session.session_id, repo_root=repo_root)
            try:
                diagnostics = await hook_runner.dispatch_observe(
                    "session_shutdown",
                    {"session_id": session.session_id},
                    hook_ctx,
                )
            except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
                hook_ctx.logger.warn("hook observe dispatch failed", event="session_shutdown", error=str(exc))
                continue
            _log_hook_diagnostics(hook_ctx=hook_ctx, event="session_shutdown", diagnostics=diagnostics)

        if not has_more:
            break
        offset += len(sessions)


def _log_hook_diagnostics(
    *,
    hook_ctx: HookContext,
    event: str,
    diagnostics: tuple[HookExecution, ...],
) -> None:
    """Log non-success hook results while keeping main shutdown path fail-open."""
    for item in diagnostics:
        if item.status == "ok":
            continue
        hook_ctx.logger.warn(
            "hook execution isolated",
            event=event,
            hook_id=item.hook_id,
            status=item.status,
            duration_ms=item.duration_ms,
            error=item.error,
        )
