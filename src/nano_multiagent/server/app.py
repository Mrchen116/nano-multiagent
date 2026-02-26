import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from nano_multiagent import __version__
from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.ids import make_event_id
from nano_multiagent.session.service import SessionService
from nano_multiagent.session.stores.base import SessionStore

from .deps import APIError, get_trace_id
from .routes.global_routes import router as global_router
from .routes.session import router as session_router


def create_app(
    *,
    session_store: SessionStore | None = None,
    runtime: AgentRuntime | None = None,
    auth_token: str | None = None,
) -> FastAPI:
    app = FastAPI(title="nano-multiagent", version=__version__)
    session_service = SessionService(store=session_store)
    app.state.session_service = session_service
    app.state.agent_runtime = runtime or AgentRuntime(session_manager=session_service.manager)
    app.state.auth_token = auth_token if auth_token is not None else os.getenv("NANO_MULTIAGENT_API_TOKEN")

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next: Any):  # type: ignore[valid-type]
        incoming_trace_id = request.headers.get("X-Request-Id", "").strip()
        request.state.trace_id = incoming_trace_id or make_event_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.trace_id
        return response

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return _error_response(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            status_code=exc.status_code,
            trace_id=get_trace_id(request),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        code = "http_error"
        if exc.status_code == 401:
            code = "unauthorized"
        elif exc.status_code == 404:
            code = "not_found"
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        return _error_response(
            code=code,
            message=detail,
            retryable=False,
            status_code=exc.status_code,
            trace_id=get_trace_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            code="invalid_request",
            message=str(exc).replace("\n", "; "),
            retryable=False,
            status_code=422,
            trace_id=get_trace_id(request),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
        return _error_response(
            code="internal_error",
            message="internal server error",
            retryable=False,
            status_code=500,
            trace_id=get_trace_id(request),
        )

    app.include_router(global_router)
    app.include_router(session_router)
    return app


def _error_response(
    *,
    code: str,
    message: str,
    retryable: bool,
    status_code: int,
    trace_id: str,
) -> JSONResponse:
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


app = create_app()
