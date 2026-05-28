"""Shared test helpers for integration tests.

_ASGIClient wraps a FastAPI/Starlette app synchronously to avoid the
cross-event-loop incompatibility that arises when httpx.AsyncClient is handed
a sync _AsyncTransportBridge in REPL tests: SSE streaming is handled here via
Starlette's synchronous TestClient.stream(), then yielded as an async generator
so REPL loop code can iterate it normally.
"""

from typing import Any

from starlette.testclient import TestClient as _StarletteTestClient

from coding_cli.client import _IncrementalSseParser


class ASGIClient:
    """Synchronous ASGI client that exposes the ServerClient interface.

    Used in REPL integration tests to avoid asyncio event-loop nesting issues
    that arise when ServerClient (httpx.AsyncClient) is given an ASGITransport.
    """

    def __init__(self, app: Any) -> None:
        self._app = app
        self._sync = _StarletteTestClient(app, raise_server_exceptions=True)

    def __enter__(self) -> "ASGIClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass

    def health(self) -> dict[str, Any]:
        resp = self._sync.get("/v1/health")
        resp.raise_for_status()
        return resp.json()

    def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: str | None = None,
        skills: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"workspace_root": workspace_root or "/tmp/test"}
        if title is not None:
            payload["title"] = title
        if skills is not None:
            payload["skills"] = skills
        resp = self._sync.post(
            "/v1/sessions",
            json=payload,
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-create"},
        )
        resp.raise_for_status()
        return resp.json()

    def submit_message(
        self,
        *,
        session_id: str,
        text: str,
        priority: str = "next",
        message_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}], "priority": priority}
        if message_id is not None:
            payload["message_id"] = message_id
        resp = self._sync.post(
            f"/v1/sessions/{session_id}/messages",
            json=payload,
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-submit"},
        )
        resp.raise_for_status()
        return resp.json()

    async def stream_session(
        self, *, session_id: str, last_event_id: int | None = None
    ):
        # Each stream_session call creates a fresh TestClient to avoid thread-safety
        # issues: the background SessionStreamReader calls stream_session() from a
        # dedicated thread, while other methods use self._sync from the main thread.
        stream_client = _StarletteTestClient(self._app, raise_server_exceptions=True)
        headers: dict[str, str] = {
            "Authorization": "Bearer test-token",
            "Accept": "text/event-stream",
            "X-Request-Id": "req-asgi-stream",
        }
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)
        parser = _IncrementalSseParser()
        with stream_client.stream("GET", f"/v1/sessions/{session_id}/stream", headers=headers) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                for event in parser.feed(chunk):
                    yield event

    def get_session(self, *, session_id: str) -> dict[str, Any]:
        resp = self._sync.get(
            f"/v1/sessions/{session_id}",
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-get"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_session_messages(self, *, session_id: str, limit: int = 100) -> dict[str, Any]:
        resp = self._sync.get(
            f"/v1/sessions/{session_id}/messages",
            params={"limit": limit},
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-msgs"},
        )
        resp.raise_for_status()
        return resp.json()

    def list_session_tools(self, *, session_id: str) -> dict[str, Any]:
        resp = self._sync.get(
            f"/v1/sessions/{session_id}/tools",
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-tools"},
        )
        resp.raise_for_status()
        return resp.json()

    def compact_session(self, *, session_id: str) -> dict[str, Any]:
        resp = self._sync.post(
            f"/v1/sessions/{session_id}:compact",
            json={},
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-compact"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_session_history(self, *, session_id: str, limit: int = 50) -> dict[str, Any]:
        resp = self._sync.get(
            f"/v1/sessions/{session_id}/history",
            params={"limit": limit},
            headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-asgi-history"},
        )
        resp.raise_for_status()
        return resp.json()
