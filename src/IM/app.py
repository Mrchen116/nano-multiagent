"""FastAPI application for the independent IM service."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from IM.api.routes.account import router as account_router
from IM.api.routes.agents import router as agent_router
from IM.api.routes.messages import router as message_router
from IM.api.routes.metrics import router as metrics_router
from IM.api.routes.nodes import router as nodes_router
from IM.api.routes.users import router as user_router
from IM.api.routes.web_im import router as web_im_router
from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import EventRepository, NodeRepository
from IM.ws.gateway_handler import GatewayHandler


def _resolve_frontend_dist_dir(frontend_dist_dir: Path | None) -> Path:
    """Return the built Web IM asset directory for the running IM service."""
    if frontend_dist_dir is not None:
        return frontend_dist_dir
    return Path(os.getenv("IM_FRONTEND_DIST_DIR", Path(__file__).resolve().parent / "frontend" / "dist"))


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
    frontend_dist_dir: Path,
    frontend_dev_base_url: str,
) -> None:
    """Expose discoverable Web IM entry routes on the IM service host."""
    index_html_path = frontend_dist_dir / "index.html"
    favicon_path = frontend_dist_dir / "favicon.svg"
    assets_dir = frontend_dist_dir / "assets"
    serve_built_frontend = index_html_path.is_file()

    def frontend_entry_response(request: Request):
        if serve_built_frontend:
            return FileResponse(index_html_path)
        return RedirectResponse(
            url=_build_frontend_redirect_url(request, frontend_dev_base_url=frontend_dev_base_url),
            status_code=307,
        )

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="im-frontend-assets")

    if favicon_path.is_file():
        @app.get("/favicon.svg", include_in_schema=False)
        async def frontend_favicon() -> FileResponse:
            """Serve the built frontend favicon from the IM service host."""
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
    resolved_frontend_dist_dir = _resolve_frontend_dist_dir(frontend_dist_dir)
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
        app_instance.state.gateway_handler = GatewayHandler(
            relay_service=RelayService(connection),
            node_repository=NodeRepository(connection),
            event_repository=EventRepository(connection),
        )
        try:
            yield
        finally:
            connection.close()

    app = FastAPI(title="Independent IM Service", version="0.1.0", lifespan=lifespan)
    app.state.upload_dir = resolved_upload_dir
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
    app.include_router(metrics_router)
    _install_frontend_entrypoints(
        app,
        frontend_dist_dir=resolved_frontend_dist_dir,
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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("IM.app:app", host="127.0.0.1", port=8011, reload=False)
