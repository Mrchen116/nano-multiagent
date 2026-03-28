"""FastAPI application for the independent IM service."""

from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from IM.api.routes.account import router as account_router
from IM.api.routes.agents import router as agent_router
from IM.api.routes.messages import router as message_router
from IM.api.routes.metrics import router as metrics_router
from IM.api.routes.nodes import router as nodes_router
from IM.api.routes.policies import router as policies_router
from IM.api.routes.users import router as user_router
from IM.api.routes.web_im import router as web_im_router
from IM.application.event_service import EventService
from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.domain.models import ConversationEvent
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import ConversationRepository, EventRepository, MessageRepository, NodeRepository, UsageMetricsRepository
from IM.ws.gateway_handler import GatewayHandler
from IM.ws.user_stream import UserStreamRegistry, build_notify_enqueue, pump_user_stream_outbound, serve_user_websocket


def _normalize_runtime_path(path: Path) -> Path:
    """Return a stable absolute path snapshot for runtime lookups."""
    return path.expanduser().resolve(strict=False)


def _discover_repo_root(start_dir: Path) -> Path | None:
    """Resolve the canonical repository root for a main checkout or git worktree."""
    current = start_dir
    while True:
        dot_git_path = current / ".git"
        if dot_git_path.is_dir():
            return current
        if dot_git_path.is_file():
            gitdir_line = dot_git_path.read_text(encoding="utf-8").strip()
            if not gitdir_line.startswith("gitdir:"):
                return current
            gitdir_value = gitdir_line.partition(":")[2].strip()
            gitdir_path = Path(gitdir_value)
            if not gitdir_path.is_absolute():
                gitdir_path = current / gitdir_path
            gitdir_path = gitdir_path.resolve(strict=False)
            if gitdir_path.name == ".git":
                return gitdir_path.parent
            for parent in gitdir_path.parents:
                if parent.name == ".git":
                    return parent.parent
            return None
        if current.parent == current:
            return None
        current = current.parent


def _resolve_frontend_dist_candidates(frontend_dist_dir: Path | None) -> tuple[Path, ...]:
    """Return ordered frontend dist candidates for runtime serving and fallback."""
    source_root = Path(__file__).resolve().parents[2]
    module_frontend_dist_dir = Path(__file__).resolve().parent / "frontend" / "dist"
    repo_root = _discover_repo_root(source_root)

    candidate_paths: list[Path] = []
    if frontend_dist_dir is not None:
        candidate_paths.append(frontend_dist_dir)
    configured_frontend_dist = os.getenv("IM_FRONTEND_DIST_DIR")
    if configured_frontend_dist:
        candidate_paths.append(Path(configured_frontend_dist))
    candidate_paths.append(module_frontend_dist_dir)
    if repo_root is not None:
        candidate_paths.append(repo_root / "src" / "IM" / "frontend" / "dist")

    deduped_paths: list[Path] = []
    seen_paths: set[str] = set()
    for candidate_path in candidate_paths:
        normalized_candidate_path = _normalize_runtime_path(candidate_path)
        normalized_key = str(normalized_candidate_path)
        if normalized_key in seen_paths:
            continue
        seen_paths.add(normalized_key)
        deduped_paths.append(normalized_candidate_path)
    return tuple(deduped_paths)


def _resolve_frontend_dist_dir(frontend_dist_dir: Path | None) -> Path:
    """Return the primary built Web IM asset directory for the running IM service."""
    return _resolve_frontend_dist_candidates(frontend_dist_dir)[0]


def _resolve_frontend_file(frontend_dist_dirs: tuple[Path, ...], relative_path: Path) -> Path | None:
    """Return the first available frontend file across runtime dist candidates."""
    for frontend_dist_dir in frontend_dist_dirs:
        candidate_path = frontend_dist_dir / relative_path
        if candidate_path.is_file():
            return candidate_path
    return None


def _resolve_frontend_asset_file(frontend_dist_dirs: tuple[Path, ...], asset_path: str) -> Path | None:
    """Return the first available frontend asset file while rejecting path traversal."""
    requested_asset_path = Path(asset_path)
    if requested_asset_path.is_absolute() or ".." in requested_asset_path.parts:
        return None
    return _resolve_frontend_file(frontend_dist_dirs, Path("assets") / requested_asset_path)


def _build_frontend_redirect_url(request: Request, *, frontend_dev_base_url: str) -> str:
    """Preserve path/query when redirecting entry traffic to the frontend dev server."""
    target = f"{frontend_dev_base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return target


def _resolve_upload_dir(*, upload_dir: Path | None, db_path: Path) -> Path:
    """Return the directory used for IM-hosted attachment uploads."""
    if upload_dir is not None:
        return upload_dir
    configured = os.getenv("IM_UPLOAD_DIR")
    if configured:
        return Path(configured)
    return db_path.parent / "uploads"


def _install_frontend_entrypoints(
    app: FastAPI,
    *,
    frontend_dist_dirs: tuple[Path, ...],
    frontend_dev_base_url: str,
) -> None:
    """Expose discoverable Web IM entry routes on the IM service host."""

    def frontend_entry_response(request: Request):
        index_html_path = _resolve_frontend_file(frontend_dist_dirs, Path("index.html"))
        if index_html_path is not None:
            return FileResponse(index_html_path)
        return RedirectResponse(
            url=_build_frontend_redirect_url(request, frontend_dev_base_url=frontend_dev_base_url),
            status_code=307,
        )

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    async def frontend_asset(asset_path: str) -> FileResponse:
        """Serve the first available built frontend asset across runtime dist candidates."""
        asset_file_path = _resolve_frontend_asset_file(frontend_dist_dirs, asset_path)
        if asset_file_path is None:
            raise HTTPException(status_code=404, detail="frontend asset not found")
        return FileResponse(asset_file_path)

    @app.get("/favicon.svg", include_in_schema=False)
    async def frontend_favicon() -> FileResponse:
        """Serve the built frontend favicon from the IM service host."""
        favicon_path = _resolve_frontend_file(frontend_dist_dirs, Path("favicon.svg"))
        if favicon_path is None:
            raise HTTPException(status_code=404, detail="frontend favicon not found")
        return FileResponse(favicon_path)

    @app.get("/", include_in_schema=False)
    async def frontend_root(request: Request):
        """Serve or forward the discoverable Web IM root entry."""
        return frontend_entry_response(request)

    @app.get("/chat", include_in_schema=False)
    @app.get("/chat/{conversation_path:path}", include_in_schema=False)
    async def frontend_chat_entry(request: Request, conversation_path: str = ""):
        """Serve or forward the Web IM chat shell for SPA routes."""
        del conversation_path
        return frontend_entry_response(request)

    @app.get("/settings", include_in_schema=False)
    @app.get("/settings/{settings_path:path}", include_in_schema=False)
    async def frontend_settings_entry(request: Request, settings_path: str = ""):
        """Serve or forward the Web IM settings shell for SPA routes."""
        del settings_path
        return frontend_entry_response(request)

    @app.get("/bind/confirm", include_in_schema=False)
    async def frontend_bind_confirm_entry(request: Request):
        """Serve or forward the bind confirmation shell on the IM host."""
        return frontend_entry_response(request)


def create_app(
    *,
    db_path: Path | None = None,
    frontend_dist_dir: Path | None = None,
    frontend_dev_base_url: str | None = None,
    upload_dir: Path | None = None,
) -> FastAPI:
    """Build a standalone IM FastAPI application.

    Args:
        db_path: Optional SQLite file path used by the IM service.
        frontend_dist_dir: Optional built frontend asset directory served on the IM host.
        frontend_dev_base_url: Optional fallback dev-server base URL used when built assets are absent.
        upload_dir: Optional directory where IM-hosted attachment uploads are stored.

    Returns:
        FastAPI app with initialized storage and IM routes.

    Side Effects:
        Creates the SQLite file if missing and initializes schema at startup.
    """
    resolved_db_path = db_path or Path(os.getenv("IM_DB_PATH", "data/im_service.sqlite3"))
    resolved_frontend_dist_dirs = _resolve_frontend_dist_candidates(frontend_dist_dir)
    resolved_frontend_dev_base_url = frontend_dev_base_url or os.getenv("IM_FRONTEND_DEV_BASE_URL", "http://127.0.0.1:4173")
    resolved_upload_dir = _resolve_upload_dir(upload_dir=upload_dir, db_path=resolved_db_path)
    resolved_upload_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        """Manage app-level SQLite connection lifecycle."""
        connection = connect(resolved_db_path)
        initialize_schema(connection)
        app_instance.state.connection = connection
        app_instance.state.upload_dir = resolved_upload_dir

        registry = UserStreamRegistry()
        outbound_queue: asyncio.Queue[tuple[frozenset[str], str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # EventService 依赖 EventRepository；notify 又需 EventService 做 enrich，故用桥接稍后注入实现。
        _user_notify_impl: list[object] = [None]

        def user_event_notify(event: ConversationEvent) -> None:
            impl = _user_notify_impl[0]
            if impl is not None:
                impl(event)  # type: ignore[misc]

        app_instance.state.user_stream_registry = registry
        app_instance.state.user_event_notify = user_event_notify

        event_repository = EventRepository(connection, notify=user_event_notify)
        message_repository = MessageRepository(connection, notify=user_event_notify)
        event_service = EventService(events=event_repository)
        _user_notify_impl[0] = build_notify_enqueue(
            connection=connection,
            outbound_queue=outbound_queue,
            loop=loop,
            event_service=event_service,
        )
        app_instance.state.event_repository = event_repository
        app_instance.state.message_repository = message_repository

        pump_task = asyncio.create_task(pump_user_stream_outbound(registry=registry, outbound_queue=outbound_queue))
        app_instance.state.user_stream_pump_task = pump_task

        app_instance.state.gateway_handler = GatewayHandler(
            relay_service=RelayService(connection),
            node_repository=NodeRepository(connection),
            event_repository=event_repository,
            metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
            conversation_repository=ConversationRepository(connection),
            user_event_notify=user_event_notify,
        )
        try:
            yield
        finally:
            pump_task.cancel()
            try:
                await pump_task
            except asyncio.CancelledError:
                pass
            connection.close()

    app = FastAPI(title="Independent IM Service", version="0.1.0", lifespan=lifespan)
    app.state.upload_dir = resolved_upload_dir
    app.state.frontend_dist_dirs = resolved_frontend_dist_dirs
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/im/uploads", StaticFiles(directory=resolved_upload_dir), name="im-uploads")
    app.include_router(user_router)
    app.include_router(account_router)
    app.include_router(agent_router)
    app.include_router(web_im_router)
    app.include_router(message_router)
    app.include_router(nodes_router)
    app.include_router(policies_router)
    app.include_router(metrics_router)
    _install_frontend_entrypoints(
        app,
        frontend_dist_dirs=resolved_frontend_dist_dirs,
        frontend_dev_base_url=resolved_frontend_dev_base_url,
    )

    @app.websocket("/im/ws/gateway")
    async def gateway_websocket(websocket: WebSocket) -> None:
        """Serve the Gateway websocket protocol used by IM relay delivery."""
        try:
            await app.state.gateway_handler.serve(websocket)
        except ValueError as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "payload": {"code": "invalid_message", "message": str(exc)},
                }
            )
            await websocket.close(code=1003)

    @app.websocket("/im/ws/user")
    async def user_stream_websocket(websocket: WebSocket) -> None:
        """浏览器用户实时事件流（每用户一条或多标签多条连接）。"""
        user_id = (websocket.query_params.get("user_id") or "").strip()
        if not user_id:
            await websocket.close(code=1008)
            return
        await serve_user_websocket(
            websocket=websocket,
            connection=app.state.connection,
            registry=app.state.user_stream_registry,
            user_id=user_id,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("IM.app:app", host="127.0.0.1", port=8011, reload=False)
