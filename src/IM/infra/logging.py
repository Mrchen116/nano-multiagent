"""Keep one-use browser credentials out of every IM server startup mode."""

import logging
import re


class RedactCredentials(logging.Filter):
    """Remove query credentials from Uvicorn's WebSocket handshake messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(
            r"([?&](?:ticket|token|access_token|refresh_token)=)[^&\s\"']+",
            r"\1[redacted]",
            record.getMessage(),
        )
        record.args = ()
        return True


def redact_server_credentials() -> None:
    """Install idempotent filters on the actual Uvicorn HTTP and WS loggers."""
    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, RedactCredentials) for item in logger.filters):
            logger.addFilter(RedactCredentials())
