import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class ServerClientConfig:
    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    request_id: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "ServerClientConfig":
        timeout_text = os.getenv("NANO_MULTIAGENT_API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        return cls(
            base_url=os.getenv("NANO_MULTIAGENT_API_BASE_URL", DEFAULT_BASE_URL),
            token=os.getenv("NANO_MULTIAGENT_API_TOKEN"),
            request_id=os.getenv("NANO_MULTIAGENT_REQUEST_ID"),
            timeout_seconds=float(timeout_text),
        )


class ServerClient:
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
        self._client.close()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", require_auth=False)

    def create_session(self, *, title: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        return self._request("POST", "/v1/sessions", json=payload, require_auth=True)

    def send_message(self, *, session_id: str, text: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not text.strip():
            raise ValueError("text is required")
        payload = {
            "parts": [{"type": "text", "text": text}],
            "stream": False,
        }
        return self._request(
            "POST",
            f"/v1/sessions/{session_id}/messages",
            json=payload,
            require_auth=True,
        )

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not text.strip():
            raise ValueError("text is required")
        payload = {
            "parts": [{"type": "text", "text": text}],
        }
        return self._request(
            "POST",
            f"/v1/sessions/{session_id}/messages:async",
            json=payload,
            require_auth=True,
        )

    def get_run(self, *, run_id: str) -> dict[str, Any]:
        if not run_id.strip():
            raise ValueError("run_id is required")
        return self._request("GET", f"/v1/runs/{run_id}", require_auth=True)

    def list_session_tools(self, *, session_id: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request(
            "GET",
            f"/v1/sessions/{session_id}/tools",
            require_auth=True,
        )

    def compact_session(self, *, session_id: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request(
            "POST",
            f"/v1/sessions/{session_id}:compact",
            json={},
            require_auth=True,
        )

    def get_context_budget(self, *, session_id: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        return self._request(
            "GET",
            f"/v1/sessions/{session_id}/context-budget",
            require_auth=True,
        )

    def get_llm_config(self) -> dict[str, Any]:
        return self._request("GET", "/v1/llm-config", require_auth=True)

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
        return self._request("PATCH", "/v1/llm-config", json=payload, require_auth=True)

    def patch_llm_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._request(
            "PATCH",
            "/v1/llm-config",
            json=payload,
            require_auth=True,
        )

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, Any]]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        if max_events <= 0:
            raise ValueError("max_events must be > 0")
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be >= 0")

        headers = self._build_headers(require_auth=True)
        response = self._client.request(
            method="GET",
            url=f"/v1/sessions/{session_id}/events",
            params={
                "max_events": max_events,
                "timeout_seconds": timeout_seconds,
            },
            headers=headers,
        )

        if response.status_code >= 400:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = {"raw": response.text}
            raise RuntimeError(f"request failed ({response.status_code}): {payload}")

        return _parse_sse_events(response.text)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        require_auth: bool,
    ) -> dict[str, Any]:
        headers = self._build_headers(require_auth=require_auth)
        response = self._client.request(method=method, url=path, json=json, headers=headers)

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        if response.status_code >= 400:
            raise RuntimeError(f"request failed ({response.status_code}): {payload}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected response payload: {type(payload).__name__}")
        return payload

    def _build_headers(self, *, require_auth: bool) -> dict[str, str]:
        request_id = self._config.request_id or f"req-cli-{uuid.uuid4().hex[:8]}"
        headers = {"X-Request-Id": request_id}
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        elif require_auth:
            raise ValueError("missing API token: set --token or NANO_MULTIAGENT_API_TOKEN")
        return headers


def _wrap_transport(transport: httpx.BaseTransport | None) -> httpx.BaseTransport | None:
    if transport is None:
        return None
    if hasattr(transport, "handle_request"):
        return transport
    if hasattr(transport, "handle_async_request"):
        return _AsyncTransportBridge(transport)  # type: ignore[arg-type]
    return transport


def _should_trust_env(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
    return host not in local_hosts


def _parse_sse_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        segment = block.strip()
        if not segment:
            continue
        event_id: str | None = None
        event = "message"
        data_lines: list[str] = []
        for line in segment.splitlines():
            if line.startswith("id:"):
                event_id = line[3:].strip()
                continue
            if line.startswith("event:"):
                event = line[6:].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
                continue
        if not data_lines:
            continue
        data_text = "\n".join(data_lines)
        try:
            parsed = json.loads(data_text)
        except ValueError:
            continue
        if not isinstance(parsed, dict):
            continue
        events.append(
            {
                "event_id": event_id or "",
                "event": event,
                "data": parsed,
            }
        )
    return events


class _AsyncTransportBridge(httpx.BaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
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
        if hasattr(self._transport, "aclose"):
            asyncio.run(self._transport.aclose())
