"""HTTP client contract owned by the coding_cli package."""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class ServerClientConfig:
    """Configure coding_cli HTTP transport defaults."""

    base_url: str = DEFAULT_BASE_URL
    request_id: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "ServerClientConfig":
        """Load config from coding_cli environment variables."""
        timeout_text = os.getenv("NANO_MULTIAGENT_API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        return cls(
            base_url=os.getenv("NANO_MULTIAGENT_API_BASE_URL", DEFAULT_BASE_URL),
            request_id=os.getenv("NANO_MULTIAGENT_REQUEST_ID"),
            timeout_seconds=float(timeout_text),
        )


class ServerClient:
    """Call the local agent HTTP API from coding_cli.

    Notes:
        The CLI may only cross the package boundary through HTTP. This client is
        therefore package-owned instead of importing Python symbols from
        ``agent``.
    """

    def __init__(
        self,
        *,
        config: ServerClientConfig | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config or ServerClientConfig.from_env()
        resolved_transport = _wrap_transport(transport)
        self._transport = resolved_transport
        trust_env = _should_trust_env(self._config.base_url)
        self._client = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            transport=resolved_transport,
            trust_env=trust_env,
        )

    def __enter__(self) -> "ServerClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self.close()

    def close(self) -> None:
        """Release underlying HTTP transport resources."""
        self._client.close()

    def health(self) -> dict[str, Any]:
        """Call unauthenticated health endpoint."""
        return self._request("GET", "/v1/health")

    def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: str | None = None,
        skills: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a session through the HTTP API."""
        payload: dict[str, Any] = {"workspace_root": workspace_root or os.getcwd()}
        if title is not None:
            payload["title"] = title
        if skills is not None:
            payload["skills"] = skills
        return self._request("POST", "/v1/sessions", json=payload)

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /messages. Returns {run_id, anchor_sequence, injected, status}."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not text.strip():
            raise ValueError("text is required")
        payload: dict[str, Any] = {
            "parts": [{"type": "text", "text": text}],
            "priority": priority,
        }
        if message_id is not None:
            payload["message_id"] = message_id
        return self._request(
            "POST",
            f"/v1/sessions/{session_id}/messages",
            json=payload,
        )

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """GET /stream as persistent SSE iterator.

        Yields decoded events {"event": str, "_id": int, **payload}.
        Closes only when HTTP connection closes.
        """
        if not session_id.strip():
            raise ValueError("session_id is required")
        headers = self._build_headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        async with httpx.AsyncClient(
            base_url=self._config.base_url,
            transport=self._transport,
        ) as client:
            async with client.stream(
                "GET",
                f"/v1/sessions/{session_id}/stream",
                headers=headers,
                timeout=None,
            ) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(f"stream_session failed: {resp.status_code}")
                parser = _IncrementalSseParser()
                async for chunk in resp.aiter_bytes():
                    for event in parser.feed(chunk):
                        yield event

    def get_run(self, *, run_id: str) -> dict[str, Any]:
        """Fetch run status snapshot for polling-based async flows."""
        if not run_id.strip():
            raise ValueError("run_id is required")
        return self._request("GET", f"/v1/runs/{run_id}")

    def list_session_tools(self, *, session_id: str) -> dict[str, Any]:
        """List tool descriptors exposed to one session."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request("GET", f"/v1/sessions/{session_id}/tools")

    def compact_session(self, *, session_id: str) -> dict[str, Any]:
        """Trigger manual session compaction."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request(
            "POST",
            f"/v1/sessions/{session_id}:compact",
            json={},
        )

    def get_context_budget(self, *, session_id: str) -> dict[str, Any]:
        """Fetch context budget snapshot for REPL budget hints."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request("GET", f"/v1/sessions/{session_id}/context-budget")

    def get_session_messages(self, *, session_id: str, limit: int = 20) -> dict[str, Any]:
        """Fetch persisted message history for one session."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if limit <= 0:
            raise ValueError("limit must be > 0")
        return self._request(
            "GET",
            f"/v1/sessions/{session_id}/messages",
            params={"limit": limit},
        )

    def get_llm_config(self) -> dict[str, Any]:
        """Get active LLM configuration."""
        return self._request("GET", "/v1/llm-config")

    def set_llm_config(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, Any]:
        """Validate and patch runtime LLM config via the HTTP API."""
        payload: dict[str, Any] = {}
        if provider is not None:
            resolved_provider = provider.strip()
            if not resolved_provider:
                raise ValueError("provider must be a non-empty string")
            payload["provider"] = resolved_provider
        if model is not None:
            resolved_model = model.strip()
            if not resolved_model:
                raise ValueError("model must be a non-empty string")
            payload["model"] = resolved_model
        if base_url is not None:
            resolved_base_url = base_url.strip()
            if not resolved_base_url:
                raise ValueError("base_url must be a non-empty string")
            payload["base_url"] = resolved_base_url
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be > 0")
            payload["timeout_seconds"] = timeout_seconds
        if api_key is not None:
            payload["api_key"] = api_key
        if clear_api_key:
            payload["api_key"] = None
        if not payload:
            raise ValueError("llm config update requires at least one field")
        return self._request("PATCH", "/v1/llm-config", json=payload)

    def patch_llm_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Pass through partial LLM config payload without local normalization."""
        return self._request("PATCH", "/v1/llm-config", json=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON request and map HTTP errors to RuntimeError payloads."""
        headers = self._build_headers()
        response = self._client.request(method=method, url=path, json=json, headers=headers, params=params)

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        if response.status_code >= 400:
            raise RuntimeError(f"request failed ({response.status_code}): {payload}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected response payload: {type(payload).__name__}")
        return payload

    def _build_headers(self) -> dict[str, str]:
        """Build headers with request correlation."""
        request_id = self._config.request_id or f"req-cli-{uuid.uuid4().hex[:8]}"
        return {"X-Request-Id": request_id}


def _wrap_transport(transport: httpx.BaseTransport | None) -> httpx.BaseTransport | None:
    """Adapt async test transport objects for sync `httpx.Client` usage."""
    if transport is None:
        return None
    if hasattr(transport, "handle_request"):
        return transport
    if hasattr(transport, "handle_async_request"):
        return _AsyncTransportBridge(transport)  # type: ignore[arg-type]
    return transport


def _should_trust_env(base_url: str) -> bool:
    """Disable proxy inheritance for loopback targets."""
    host = (urlparse(base_url).hostname or "").strip().lower()
    local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
    return host not in local_hosts


class _IncrementalSseParser:
    """Line-level SSE parser that consumes byte chunks and yields complete events.

    Supports multi-line data, comment skipping, and cross-chunk frame boundaries.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._event_name: str = "message"
        self._event_id: str | None = None
        self._data_lines: list[str] = []
        self._events: list[dict[str, Any]] = []

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        """Feed a byte chunk and return any newly completed events."""
        self._buffer.extend(chunk)
        while b"\n" in self._buffer:
            idx = self._buffer.index(b"\n")
            line = self._buffer[:idx]
            del self._buffer[: idx + 1]
            self._process_line(line.decode("utf-8", errors="replace").rstrip("\r"))
        completed = list(self._events)
        self._events.clear()
        return completed

    def _process_line(self, line: str) -> None:
        if line == "":
            # Empty line terminates one event frame
            if self._data_lines:
                self._emit_event()
            self._event_name = "message"
            self._event_id = None
            self._data_lines = []
            return
        if line.startswith(":"):
            return  # comment
        if ":" in line:
            field, value = line.split(":", 1)
            value = value.lstrip(" ")
        else:
            field = line
            value = ""
        if field == "event":
            self._event_name = value or "message"
        elif field == "id":
            self._event_id = value
        elif field == "data":
            self._data_lines.append(value)

    def _emit_event(self) -> None:
        data_text = "\n".join(self._data_lines)
        try:
            parsed = json.loads(data_text)
        except ValueError:
            return
        if not isinstance(parsed, dict):
            return
        event: dict[str, Any] = {"event": self._event_name, **parsed}
        if self._event_id is not None:
            try:
                event["_id"] = int(self._event_id)
            except ValueError:
                event["_id"] = self._event_id
        self._events.append(event)


class _AsyncTransportBridge(httpx.BaseTransport):
    """Bridge async transport to sync interface for deterministic tests."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle sync request by delegating to an async transport event loop."""
        return asyncio.run(self._handle_request(request))

    async def _handle_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._transport.handle_async_request(request)
        body = await response.aread()
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=body,
            request=request,
            extensions=response.extensions,
        )

    def close(self) -> None:
        """Close bridged async transport when supported."""
        if hasattr(self._transport, "aclose"):
            asyncio.run(self._transport.aclose())


__all__ = ["ServerClient", "ServerClientConfig"]
