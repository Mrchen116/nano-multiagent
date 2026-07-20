"""Bootstrap IM node ownership outside the Gateway composition root."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import webbrowser
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol
from urllib.parse import parse_qs, urlparse

import httpx

from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)

_log = logging.getLogger("personal_assistant.gateway.im_bootstrap")
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
BootstrapClientFactory = Callable[[str], httpx.Client]
FeedbackSink = Callable[[str, str, str | None], None]


class GatewayStartupError(RuntimeError):
    """Represent one actionable startup failure shown to gateway operators.

    Args:
        summary: Human-readable failure summary.
        next_step: Optional concrete remediation step shown alongside the error.
    """

    def __init__(self, *, summary: str, next_step: str | None = None) -> None:
        cleaned_summary = summary.strip()
        cleaned_next_step = (
            next_step.strip()
            if isinstance(next_step, str) and next_step.strip()
            else None
        )
        super().__init__(cleaned_summary)
        self.summary = cleaned_summary
        self.next_step = cleaned_next_step


class BrowserOpener(Protocol):
    """Describe the minimal browser-launch interface needed by bind bootstrap."""

    def __call__(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        """Open one browser URL and report whether a handler accepted the request."""


def emit_gateway_feedback(
    level: str, summary: str, next_step: str | None = None
) -> None:
    """Print one operator-facing gateway feedback line to stderr."""
    import sys

    if level == "ERROR":
        print("Gateway failed to start\n", file=sys.stderr)
        for line in summary.splitlines():
            print(f"  {line}", file=sys.stderr)
        if next_step is not None:
            print(f"\n  → {next_step}", file=sys.stderr)
    else:
        print(f"{level} {summary}", file=sys.stderr)
        if next_step is not None:
            print(f"  → {next_step}", file=sys.stderr)


class IMBootstrapClient:
    """Query IM ownership state and launch browser binding when a node is unbound.

    Args:
        base_url: HTTP base URL used for IM account and node APIs.
        token: Optional bearer token forwarded to IM HTTP APIs.
        client: Optional preconfigured HTTP client used by tests.
        browser_opener: Function used to open the operator browser on pending bind URLs.
        timeout_seconds: HTTP timeout used for node/bind bootstrap calls.
        monotonic: Monotonic clock source used for short startup polling windows.
        sleep: Sleep function used between node-visibility retries.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        client: httpx.Client | None = None,
        client_factory: BootstrapClientFactory | None = None,
        browser_opener: BrowserOpener = webbrowser.open,
        feedback_sink: FeedbackSink = emit_gateway_feedback,
        timeout_seconds: float = 5.0,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
        token_getter: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._base_urls = im_bootstrap_base_urls(base_url)
        self._base_headers = build_im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._clients: dict[str, httpx.Client] = {}
        self._base_url = self._base_urls[0]
        if client is not None:
            self._clients[self._base_url] = client
        self._browser_opener = browser_opener
        self._feedback_sink = feedback_sink
        self._monotonic = monotonic
        self._sleep = sleep
        self._token_getter = token_getter

    def _refresh_token(self) -> None:
        if self._token_getter is None:
            return
        token = asyncio.run(self._token_getter())
        if token:
            self._base_headers = build_im_http_headers(token)
            for client in self._clients.values():
                client.headers.update(self._base_headers)

    def ensure_node_binding(self, *, node_id: str) -> str | None:
        """Open the bind URL when the upstream node still has no owner.

        Args:
            node_id: Gateway node id that was just registered over IM websocket.

        Returns:
            The opened bind URL for unbound nodes, or `None` when the node is already owned.

        Raises:
            GatewayStartupError: When IM bootstrap APIs do not expose the registered
                node or binding cannot be started/confirmed.
        """
        self._refresh_token()
        owner_id, resolved_base_url = self._wait_for_owner(node_id=node_id)
        if owner_id:
            return None
        client = self._get_client(resolved_base_url)
        try:
            response = client.post(
                "/im/v1/bind", json={"action": "start", "node_id": node_id}
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GatewayStartupError(
                summary=f"node {node_id} could not start IM binding",
                next_step=f"Verify {resolved_base_url}/im/v1/bind is reachable, then rerun gateway.",
            ) from exc
        payload = response.json()
        bind_url = require_text(payload.get("bind_url"), field_name="bind_url")
        if os.environ.get("NANO_MULTIAGENT_AUTO_BIND") == "1":
            bind_token = extract_bind_token(bind_url)
            if not bind_token:
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind failed: bind_url missing token",
                    next_step=f"Inspect {bind_url} or unset NANO_MULTIAGENT_AUTO_BIND.",
                )
            try:
                confirm_resp = client.post(
                    "/im/v1/bind",
                    json={"action": "confirm", "bind_token": bind_token},
                )
                confirm_resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind confirm failed",
                    next_step=(
                        f"POST {resolved_base_url}/im/v1/bind with action=confirm + bind_token failed. "
                        "Verify the IM Bearer token has confirm permission, then rerun."
                    ),
                ) from exc
            self._feedback_sink(
                "INFO",
                f"node {node_id} auto-bound to IM",
                f"NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for {resolved_base_url}.",
            )
            return None
        self._browser_opener(bind_url, new=2, autoraise=True)
        self._feedback_sink(
            "ACTION",
            f"node {node_id} is waiting for IM binding",
            f"Open {bind_url} to finish binding this node.",
        )
        return bind_url

    def close(self) -> None:
        """Release the owned HTTP client."""
        seen_ids: set[int] = set()
        for client in self._clients.values():
            client_id = id(client)
            if client_id in seen_ids:
                continue
            seen_ids.add(client_id)
            client.close()

    def _wait_for_owner(self, *, node_id: str) -> tuple[str, str]:
        deadline = self._monotonic() + 5.0
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            for base_url in self._base_urls:
                try:
                    return self._get_owner_id(
                        node_id=node_id, base_url=base_url
                    ), base_url
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self._sleep(0.1)
        checked_urls = ", ".join(
            f"{base_url}/im/v1/nodes" for base_url in self._base_urls
        )
        message = f"node {node_id} did not appear in IM bootstrap"
        next_step = (
            f"Verify the IM node API is reachable at {checked_urls} and rerun gateway."
        )
        if last_error is not None:
            raise GatewayStartupError(
                summary=message, next_step=next_step
            ) from last_error
        raise GatewayStartupError(summary=message, next_step=next_step)

    def _get_owner_id(self, *, node_id: str, base_url: str) -> str:
        response = self._get_client(base_url).get("/im/v1/nodes")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("nodes response must be a list")
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            if require_text(item.get("node_id"), field_name="node_id") != node_id:
                continue
            owner_id = item.get("owner_id")
            return owner_id.strip() if isinstance(owner_id, str) else ""
        raise RuntimeError(f"node {node_id} not found")

    def _get_client(self, base_url: str) -> httpx.Client:
        client = self._clients.get(base_url)
        if client is not None:
            return client
        if self._client_factory is not None:
            client = self._client_factory(base_url)
        else:
            client = httpx.Client(
                base_url=base_url,
                headers=self._base_headers,
                timeout=self._timeout_seconds,
                trust_env=False,
            )
        self._clients[base_url] = client
        return client


def require_text(value: object, *, field_name: str) -> str:
    """Return a required non-empty text protocol field."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field_name} must be a non-empty string")
    return value.strip()


def extract_bind_token(bind_url: str) -> str | None:
    """Pull the canonical bind token from an IM bind URL."""
    parsed = urlparse(bind_url)
    query = parse_qs(parsed.query)
    tokens = query.get("token") or query.get("bind_token") or []
    return tokens[0] if tokens else None


def im_bootstrap_base_urls(url: str) -> tuple[str, ...]:
    """Return the HTTP IM endpoint candidates for bootstrap calls."""
    return (normalize_im_http_base_url(url),)
