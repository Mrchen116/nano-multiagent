"""HTTP client for the personal assistant gateway to talk to the local agent kernel."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

DEFAULT_KERNEL_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class KernelApiClientConfig:
    """Configure authentication and transport defaults for kernel HTTP calls.

    Args:
        base_url: Base HTTP URL exposed by the local kernel process.
        token: Optional bearer token used by authenticated kernel endpoints.
        request_id: Optional fixed request id used to correlate gateway-originated calls.
        timeout_seconds: Per-request timeout applied to all kernel HTTP calls.
    """

    base_url: str = DEFAULT_KERNEL_BASE_URL
    token: str | None = None
    request_id: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class KernelApiClient:
    """Expose the Node Gateway subset of the agent HTTP API.

    Notes:
        This client is the only supported HTTP boundary for `personal_assistant`
        to talk to the local kernel. It intentionally mirrors the NodeGateway-SPEC
        subset instead of importing runtime internals.
    """

    def __init__(
        self,
        *,
        config: KernelApiClientConfig | None = None,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config or KernelApiClientConfig()
        self._client = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            transport=transport,
            trust_env=_should_trust_env(self._config.base_url),
        )
        self._async_transport = async_transport

    def close(self) -> None:
        """Release underlying HTTP resources.

        Side Effects:
            Closes the owned `httpx.Client` transport pool.
        """

        self._client.close()

    def health(self) -> dict[str, Any]:
        """Call the unauthenticated kernel health endpoint."""

        return self._request("GET", "/v1/health", require_auth=False)

    def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create one kernel session bound to an agent workspace.

        Args:
            workspace_root: Absolute workspace root that the kernel binds to the session.
            product_id: Product profile identifier, expected to be `personal_assistant`.
            title: Optional operator-facing session title.
            metadata: Optional session metadata persisted by the kernel for later turns.
        """

        payload: dict[str, Any] = {
            "workspace_root": _require_non_empty_string(workspace_root, field_name="workspace_root"),
            "product_id": _require_non_empty_string(product_id, field_name="product_id"),
        }
        if title is not None:
            payload["title"] = _require_non_empty_string(title, field_name="title")
        if metadata is not None:
            payload["metadata"] = dict(metadata)
        return self._request("POST", "/v1/sessions", json=payload, require_auth=True)

    def get_session(self, *, session_id: str) -> dict[str, Any]:
        """Fetch one kernel session summary including persisted metadata."""

        session = _require_non_empty_string(session_id, field_name="session_id")
        return self._request("GET", f"/v1/sessions/{session}", require_auth=True)

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        turn_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Persist one user/assistant message into session history without running the model."""

        session = _require_non_empty_string(session_id, field_name="session_id")
        normalized_role = _require_non_empty_string(role, field_name="role").lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        payload: dict[str, Any] = {
            "role": normalized_role,
            "content": content,
            "parts": [dict(part) for part in parts or []],
            "metadata": dict(metadata or {}),
        }
        if message_id is not None:
            payload["message_id"] = _require_non_empty_string(message_id, field_name="message_id")
        if turn_id is not None:
            payload["turn_id"] = _require_non_empty_string(turn_id, field_name="turn_id")
        if idempotency_key is not None:
            payload["idempotency_key"] = _require_non_empty_string(idempotency_key, field_name="idempotency_key")
        return self._request(
            "POST",
            f"/v1/sessions/{session}/messages:append",
            json=payload,
            require_auth=True,
        )

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, Any]] | None = None,
        priority: str = "next",
    ) -> dict[str, Any]:
        """POST /messages. Returns {run_id, anchor_sequence, injected, status}."""
        if not texts:
            raise ValueError("texts must contain at least one message")
        parts: list[dict[str, Any]] = [
            {"type": "text", "text": _require_non_empty_string(t, field_name="texts[i]")} for t in texts
        ]
        for img in image_urls or []:
            url = img.get("url")
            if isinstance(url, str) and url.strip():
                image_part: dict[str, Any] = {"type": "image", "image_url": url.strip()}
                mime = img.get("content_type")
                if isinstance(mime, str) and mime.strip():
                    image_part["mime_type"] = mime.strip()
                parts.append(image_part)
        payload: dict[str, Any] = {"parts": parts, "priority": priority}
        session = _require_non_empty_string(session_id, field_name="session_id")
        return self._request(
            "POST",
            f"/v1/sessions/{session}/messages",
            json=payload,
            require_auth=True,
        )

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """GET /stream as persistent SSE iterator.

        Yields decoded events {"event": str, "_id": int, **payload}.
        """
        import asyncio
        session = _require_non_empty_string(session_id, field_name="session_id")
        headers = self._build_headers(require_auth=True)
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        async with httpx.AsyncClient(
            base_url=self._config.base_url,
            transport=self._async_transport,
        ) as client:
            async with client.stream(
                "GET",
                f"/v1/sessions/{session}/stream",
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
        """Fetch current async run status snapshot for polling flows."""

        run = _require_non_empty_string(run_id, field_name="run_id")
        return self._request("GET", f"/v1/runs/{run}", require_auth=True)

    def cancel_run(self, *, run_id: str) -> dict[str, Any]:
        """Request async run cancellation and return updated run state."""

        run = _require_non_empty_string(run_id, field_name="run_id")
        return self._request("POST", f"/v1/runs/{run}/cancel", json={}, require_auth=True)

    def interrupt_session(self, *, session_id: str) -> dict[str, Any]:
        """Force-interrupt the active run for a session and return interrupt result."""

        session = _require_non_empty_string(session_id, field_name="session_id")
        return self._request("POST", f"/v1/sessions/{session}/interrupt", json={}, require_auth=True)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        require_auth: bool,
    ) -> dict[str, Any]:
        response = self._client.request(method=method, url=path, json=json, headers=self._build_headers(require_auth=require_auth))
        _raise_for_error_response(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected response payload: {type(payload).__name__}")
        return payload

    def _build_headers(self, *, require_auth: bool) -> dict[str, str]:
        request_id = self._config.request_id or f"req-gateway-{uuid.uuid4().hex[:8]}"
        headers = {"X-Request-Id": request_id}
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        elif require_auth:
            raise ValueError("missing API token for kernel client")
        return headers


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


def _raise_for_error_response(response: httpx.Response) -> None:
    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"raw": response.text}
    if response.status_code < 400:
        return
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        code = error.get("code", "http_error")
        message = error.get("message", response.reason_phrase)
        trace_id = error.get("trace_id")
        raise RuntimeError(f"kernel request failed ({response.status_code}) code={code} message={message} trace_id={trace_id}")
    raise RuntimeError(f"kernel request failed ({response.status_code}): {payload}")


def _should_trust_env(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    return host not in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _require_non_empty_string(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()
