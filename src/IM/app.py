"""FastAPI application for the independent IM service."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI

from IM.api.routes.messages import router as message_router
from IM.api.routes.users import router as user_router
from IM.api.routes.web_im import router as web_im_router
from IM.infra.db import connect, initialize_schema


def create_app(*, db_path: Path | None = None) -> FastAPI:
    """Build a standalone IM FastAPI application.

    Args:
        db_path: Optional SQLite file path used by the IM service.

    Returns:
        FastAPI app with initialized storage and IM routes.

    Side Effects:
        Creates the SQLite file if missing and initializes schema at startup.
    """
    resolved_db_path = db_path or Path(os.getenv("IM_DB_PATH", "data/im_service.sqlite3"))

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        """Manage app-level SQLite connection lifecycle."""
        connection = connect(resolved_db_path)
        initialize_schema(connection)
        app_instance.state.connection = connection
        try:
            yield
        finally:
            connection.close()

    app = FastAPI(title="Independent IM Service", version="0.1.0", lifespan=lifespan)
    app.include_router(user_router)
    app.include_router(web_im_router)
    app.include_router(message_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("IM.app:app", host="127.0.0.1", port=8011, reload=False)
