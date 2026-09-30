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
