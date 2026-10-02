"""The public origin preserves diagnostics without printing bearer queries."""

import logging
from io import StringIO

from IM.cli.public_server import RedactCredentials


def test_websocket_accept_and_reject_logs_never_retain_query_credentials():
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(RedactCredentials())
    logger = logging.Logger("isolated-public-origin")
    logger.addHandler(handler)
    for status in ("[accepted]", "403"):
        logger.warning(
            '%s - "WebSocket %s" %s',
            "127.0.0.1:1",
            "/im/ws/user?ticket=private-ticket&token=private-token",
            status,
        )
    logged = output.getvalue()
    assert "private-ticket" not in logged
    assert "private-token" not in logged
    assert "WebSocket /im/ws/user?ticket=[redacted]&token=[redacted]" in logged
    assert "[accepted]" in logged and "403" in logged


def test_direct_uvicorn_startup_also_redacts_ticket_queries(tmp_path):
    from fastapi.testclient import TestClient
    from IM.app import create_app
    import io
    import logging

    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger("uvicorn.error")
    logger.addHandler(handler)
    try:
        with TestClient(create_app(db_path=tmp_path / "logs.db")):
            logger.warning("WebSocket /im/ws/user?ticket=%s", "private-ticket")
        assert "private-ticket" not in output.getvalue()
        assert "ticket=[redacted]" in output.getvalue()
    finally:
        logger.removeHandler(handler)
