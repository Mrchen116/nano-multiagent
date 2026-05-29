import httpx
import pytest

from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig


class _SSETransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-token"
        assert request.headers["x-request-id"] == "req-fixed"
        return httpx.Response(
            200,
            text="id: evt-1\nevent: run.update\ndata: {\"status\": \"running\"}\n\nid: evt-2\ndata: {\"status\": \"completed\"}\n\n",
        )


class _JSONTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/v1/health":
            return httpx.Response(200, json={"healthy": True, "version": "0.1.0", "node_id": "local"})
        if request.url.path == "/v1/sessions" and request.method == "POST":
            return httpx.Response(201, json={"session_id": "sess-1", "status": "idle", "created_at": "now", "metadata": {}})
        if request.url.path == "/v1/sessions/sess-1" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-1",
                    "status": "active",
                    "created_at": "now",
                    "metadata": {"workspace_root": "/tmp/agent-a", "agent_id": "agent-a"},
                },
            )
        if request.url.path == "/v1/sessions/sess-1/messages:append":
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-1",
                    "entry_id": "evt-1",
                    "kind": "session.turn.appended",
                    "created_at": "now",
                    "turn_id": "turn-1",
                    "role": "assistant",
                    "content": "hello",
                    "message_id": "msg-1",
                    "parts": [],
                    "metadata": {"idempotency_key": "idem-1"},
                },
            )
        if request.url.path == "/v1/sessions/sess-1/messages" and request.method == "POST":
            return httpx.Response(200, json={"run_id": "run-1", "session_id": "sess-1", "anchor_sequence": 1, "injected": False, "status": "queued"})
        if request.url.path == "/v1/sessions/sess-1/messages:async":
            return httpx.Response(202, json={"run_id": "run-1", "session_id": "sess-1", "status": "queued"})
        if request.url.path == "/v1/runs/run-1":
            return httpx.Response(200, json={"run_id": "run-1", "session_id": "sess-1", "status": "running", "created_at": "a", "updated_at": "b"})
        if request.url.path == "/v1/runs/run-1/cancel":
            return httpx.Response(200, json={"run_id": "run-1", "session_id": "sess-1", "status": "cancelled", "created_at": "a", "updated_at": "c"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")


EXPECTED_METHODS = {
    "health",
    "create_session",
    "append_message",
    "submit_message",
    "stream_session",
    "get_run",
    "cancel_run",
}


def test_kernel_api_client_exposes_gateway_http_subset() -> None:
    for method_name in EXPECTED_METHODS:
        assert hasattr(KernelApiClient, method_name)


def test_kernel_api_client_calls_required_http_subset() -> None:
    transport = _JSONTransport()
    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="secret-token", request_id="req-fixed"),
        transport=transport,
    )

    assert client.health()["healthy"] is True
    assert client.create_session(workspace_root="/tmp/agent-a", product_id="personal_assistant")["session_id"] == "sess-1"
    assert client.get_session(session_id="sess-1")["metadata"]["workspace_root"] == "/tmp/agent-a"
    assert client.append_message(
        session_id="sess-1",
        role="assistant",
        content="hello",
        metadata={"source": "gateway"},
        idempotency_key="idem-1",
    )["entry_id"] == "evt-1"
    assert client.submit_message(session_id="sess-1", texts=["hello"])["run_id"] == "run-1"
    assert client.get_run(run_id="run-1")["status"] == "running"
    assert client.cancel_run(run_id="run-1")["status"] == "cancelled"

    create_request = next(request for request in transport.requests if request.url.path == "/v1/sessions")
    get_request = next(request for request in transport.requests if request.url.path == "/v1/sessions/sess-1")
    append_request = next(request for request in transport.requests if request.url.path.endswith("messages:append"))
    submit_request = next(request for request in transport.requests if request.url.path.endswith("messages") and request.method == "POST")
    assert create_request.headers["authorization"] == "Bearer secret-token"
    assert create_request.headers["x-request-id"] == "req-fixed"
    assert get_request.headers["authorization"] == "Bearer secret-token"
    assert get_request.headers["x-request-id"] == "req-fixed"
    assert b'"workspace_root":"/tmp/agent-a"' in create_request.content
    assert b'"product_id":"personal_assistant"' in create_request.content
    assert b'"role":"assistant"' in append_request.content
    assert b'"content":"hello"' in append_request.content
    assert b'"idempotency_key":"idem-1"' in append_request.content
    assert b'"parts":[{"type":"text","text":"hello"}]' in submit_request.content
    assert b'"priority":"next"' in submit_request.content


def test_kernel_api_client_forwards_session_metadata_when_creating_sessions() -> None:
    transport = _JSONTransport()
    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="secret-token", request_id="req-fixed"),
        transport=transport,
    )

    created = client.create_session(
        workspace_root="/tmp/agent-a",
        product_id="personal_assistant",
        title="Agent A",
        metadata={
            "agent_id": "agent-a",
            "conversation_id": "conv-1",
            "config_profile_version": 2,
            "system_prompt": "You are Agent A v2.",
        },
    )

    assert created["session_id"] == "sess-1"
    create_request = next(request for request in transport.requests if request.url.path == "/v1/sessions")
    assert b'"title":"Agent A"' in create_request.content
    assert b'"metadata":{' in create_request.content
    assert b'"agent_id":"agent-a"' in create_request.content
    assert b'"conversation_id":"conv-1"' in create_request.content
    assert b'"config_profile_version":2' in create_request.content
    assert b'"system_prompt":"You are Agent A v2."' in create_request.content


def test_kernel_api_client_maps_error_payload_to_exception() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "session_not_found", "message": "missing", "retryable": False, "trace_id": "trace-1"}})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="secret-token"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError, match="session_not_found"):
        client.create_session(workspace_root="/tmp/agent-a", product_id="personal_assistant")


def test_kernel_api_client_requires_token_for_authenticated_calls() -> None:
    client = KernelApiClient(config=KernelApiClientConfig(base_url="http://kernel.local", token=None))

    with pytest.raises(ValueError, match="missing API token"):
        client.create_session(workspace_root="/tmp/agent-a", product_id="personal_assistant")


def test_send_message_async_includes_image_parts_when_image_urls_provided() -> None:
    """send_message_async must append type=image parts for each valid image_url entry."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(202, json={"run_id": "run-1", "session_id": "sess-1", "status": "queued"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok", request_id="req-1"),
        transport=httpx.MockTransport(handler),
    )

    client.submit_message(
        session_id="sess-1",
        texts=["describe this image"],
        image_urls=[
            {"url": "http://im.local/im/uploads/photo.png", "content_type": "image/png"},
            {"url": "http://im.local/im/uploads/doc.jpg"},
        ],
    )

    assert len(captured_requests) == 1
    body = captured_requests[0].content
    import json as _json
    parsed = _json.loads(body)
    parts = parsed["parts"]
    assert parts[0] == {"type": "text", "text": "describe this image"}
    assert parts[1] == {"type": "image", "image_url": "http://im.local/im/uploads/photo.png", "mime_type": "image/png"}
    assert parts[2] == {"type": "image", "image_url": "http://im.local/im/uploads/doc.jpg"}


def test_submit_message_without_image_urls_sends_only_text_parts() -> None:
    """submit_message without image_urls must produce only text parts."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(202, json={"run_id": "run-1", "session_id": "sess-1", "status": "queued"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok", request_id="req-1"),
        transport=httpx.MockTransport(handler),
    )

    client.submit_message(session_id="sess-1", texts=["hello"])

    import json as _json
    parsed = _json.loads(captured_requests[0].content)
    parts = parsed["parts"]
    assert len(parts) == 1
    assert parts[0] == {"type": "text", "text": "hello"}


def test_submit_message_includes_image_parts_when_image_urls_provided() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"run_id": "run-1", "session_id": "sess-1", "anchor_sequence": 1, "injected": False, "status": "queued"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok", request_id="req-1"),
        transport=httpx.MockTransport(handler),
    )

    client.submit_message(
        session_id="sess-1",
        texts=["describe this image"],
        image_urls=[
            {"url": "http://im.local/im/uploads/photo.png", "content_type": "image/png"},
            {"url": "http://im.local/im/uploads/doc.jpg"},
        ],
    )

    assert len(captured_requests) == 1
    body = captured_requests[0].content
    import json as _json
    parsed = _json.loads(body)
    parts = parsed["parts"]
    assert parts[0] == {"type": "text", "text": "describe this image"}
    assert parts[1] == {"type": "image", "image_url": "http://im.local/im/uploads/photo.png", "mime_type": "image/png"}
    assert parts[2] == {"type": "image", "image_url": "http://im.local/im/uploads/doc.jpg"}
    assert parsed["priority"] == "next"


def test_submit_message_without_image_urls_sends_only_text_parts() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"run_id": "run-1", "session_id": "sess-1", "anchor_sequence": 1, "injected": False, "status": "queued"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok", request_id="req-1"),
        transport=httpx.MockTransport(handler),
    )

    client.submit_message(session_id="sess-1", texts=["hello"])

    import json as _json
    parsed = _json.loads(captured_requests[0].content)
    parts = parsed["parts"]
    assert len(parts) == 1
    assert parts[0] == {"type": "text", "text": "hello"}
    assert parsed["priority"] == "next"


def test_incremental_sse_parser_emits_event() -> None:
    from personal_assistant.client.kernel_api_client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    chunk = b"id: 42\nevent: run_status\ndata: {\"status\":\"running\"}\n\n"
    events = parser.feed(chunk)
    assert len(events) == 1
    assert events[0]["event"] == "run_status"
    assert events[0]["_id"] == 42
    assert events[0]["status"] == "running"


def test_incremental_sse_parser_across_chunks() -> None:
    from personal_assistant.client.kernel_api_client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    events = parser.feed(b"id: 1\nevent: a\ndata: {\"x\":1}\n\n")
    assert len(events) == 1
    events = parser.feed(b"id: 2\nevent: b\ndata: {\"x\":2}\n\n")
    assert len(events) == 1
    assert events[0]["event"] == "b"
    assert events[0]["_id"] == 2


def test_incremental_sse_parser_skips_comments_and_empty() -> None:
    from personal_assistant.client.kernel_api_client import _IncrementalSseParser

    parser = _IncrementalSseParser()
    chunk = b":comment\n\nid: 3\nevent: ok\ndata: {\"y\":true}\n\n"
    events = parser.feed(chunk)
    assert len(events) == 1
    assert events[0]["event"] == "ok"
    assert events[0]["_id"] == 3


# ---------------------------------------------------------------------------
# feat-385-M3-fix-r2 B1: stream_session must forward workspace_root as query param
# ---------------------------------------------------------------------------


def test_stream_session_forwards_workspace_root_as_query_param() -> None:
    """stream_session(workspace_root=X) must include workspace_root=X in the SSE request URL.

    Refs #64: multi-agent Gateway uses per-agent workspace_root to scope sessions.
    Without workspace_root in the stream request, the kernel cannot locate the session
    JSONL and returns session_not_found 404.
    """
    import asyncio
    captured_requests: list[httpx.Request] = []

    class _CapturingAsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            # Return a minimal valid SSE stream (empty, terminates immediately).
            return httpx.Response(200, text="", headers={"content-type": "text/event-stream"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok"),
        async_transport=_CapturingAsyncTransport(),
    )

    async def _run() -> None:
        async for _ in client.stream_session(
            session_id="sess-ws",
            workspace_root="/tmp/agent-ws",
        ):
            pass

    asyncio.run(_run())

    assert captured_requests, "stream_session must have issued an HTTP request"
    stream_req = captured_requests[0]
    assert stream_req.url.path == "/v1/sessions/sess-ws/stream"
    assert "workspace_root" in stream_req.url.params, (
        "stream_session must forward workspace_root as a query parameter (Refs #64)"
    )
    assert stream_req.url.params["workspace_root"] == "/tmp/agent-ws", (
        f"workspace_root param must match the provided value; "
        f"got params: {dict(stream_req.url.params)}"
    )


def test_stream_session_without_workspace_root_omits_param() -> None:
    """stream_session without workspace_root must not send workspace_root query param."""
    import asyncio
    captured_requests: list[httpx.Request] = []

    class _CapturingAsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(200, text="", headers={"content-type": "text/event-stream"})

    client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="tok"),
        async_transport=_CapturingAsyncTransport(),
    )

    async def _run() -> None:
        async for _ in client.stream_session(session_id="sess-no-ws"):
            pass

    asyncio.run(_run())

    assert captured_requests
    stream_req = captured_requests[0]
    assert "workspace_root" not in stream_req.url.params, (
        "workspace_root param must be absent when not provided"
    )
