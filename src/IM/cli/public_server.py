"""Loopback-only single-worker public IM origin behind the local HTTPS tunnel."""

import os
import copy
from urllib.parse import urlsplit

import uvicorn

from IM.infra.logging import RedactCredentials


def main() -> None:
    """Start the bounded origin without trusting forwarded peers or logging bearer queries."""
    origin = urlsplit(os.environ.get("IM_PUBLIC_URL", ""))
    if origin.scheme != "https" or not origin.hostname:
        raise SystemExit("IM_PUBLIC_URL must name the public HTTPS origin")
    if len(os.environ.get("IM_JWT_SECRET", "")) < 32:
        raise SystemExit("IM_JWT_SECRET must contain at least 32 characters")
    if os.environ.get("WEB_CONCURRENCY", "1") != "1":
        raise SystemExit("public IM requires exactly one worker")
    os.environ["IM_PUBLIC_MODE"] = "1"
    os.environ["IM_TRUSTED_PROXY"] = "127.0.0.1"
    # access_log=False does not disable Uvicorn's WebSocket handshake logger.
    log_config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config["filters"] = {"credentials": {"()": RedactCredentials}}
    for handler in log_config["handlers"].values():
        handler["filters"] = ["credentials"]
    uvicorn.run(
        "IM.app:app",
        host="127.0.0.1",
        port=int(os.environ.get("IM_PORT", "8011")),
        workers=1,
        proxy_headers=False,
        access_log=False,
        log_config=log_config,
        ws_max_size=2 * 1024 * 1024,
        ws_max_queue=16,
        timeout_keep_alive=5,
        limit_concurrency=128,
    )


if __name__ == "__main__":
    main()
