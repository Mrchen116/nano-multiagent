"""Integration test: Gateway inbound pipeline consumes kernel SSE stream (feat-338 M8).

Verifies that the Gateway's InboundPipeline can submit a message via submit_message()
and consume the persistent SSE stream via stream_session() to extract the assistant reply.

This test uses a mocked async transport to simulate kernel SSE events, exercising the
full Gateway → KernelApiClient → SSE path without requiring a live kernel runtime.
"""

import asyncio
import json
from pathlib import Path

import httpx

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):
        pass

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        pass


class _SyncTransport(httpx.BaseTransport):
    """Sync transport mocking kernel endpoints used by Gateway."""

    def __init__(self, *, session_id: str, run_id: str) -> None:
        self._session_id = session_id
        self._run_id = run_id
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/sessions" and request.method == "POST":
            return httpx.Response(201, json={"session_id": self._session_id, "status": "idle", "created_at": "now", "metadata": {}})
        if path == f"/v1/sessions/{self._session_id}" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "session_id": self._session_id,
                    "status": "active",
                    "created_at": "now",
                    "metadata": {"workspace_root": "/tmp/agent-a", "agent_id": "agent-a"},
                },
            )
        if path == f"/v1/sessions/{self._session_id}/messages" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "run_id": self._run_id,
                    "anchor_sequence": 1,
                    "injected": False,
                    "status": "queued",
                },
            )
        raise AssertionError(f"unexpected sync request: {request.method} {path}")


class _AsyncSseTransport(httpx.AsyncBaseTransport):
    """Async transport that yields a canned SSE stream for /stream."""

    def __init__(self, *, session_id: str, run_id: str, reply_text: str) -> None:
        self._session_id = session_id
        self._run_id = run_id
        self._reply_text = reply_text

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/v1/sessions/{self._session_id}/stream" and request.method == "GET":
            body = (
                f'id: 1\nevent: run_status\ndata: {{"event":"run_status","run_id":"{self._run_id}","status":"running"}}\n\n'
                f'id: 2\nevent: assistant_message\ndata: {{"event":"assistant_message","run_id":"{self._run_id}","content":"{self._reply_text}"}}\n\n'
                f'id: 3\nevent: run_status\ndata: {{"event":"run_status","run_id":"{self._run_id}","status":"completed","usage":{{"prompt_tokens":5,"completion_tokens":3,"total_tokens":8}}}}\n\n'
            ).encode()
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)
        raise AssertionError(f"unexpected async request: {request.method} {path}")


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_a.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agent_a, title="Agent A"),
    )


def test_gateway_uses_kernel_sse_stream_for_reply(tmp_path: Path) -> None:
    """Gateway submits message and drains assistant_message + run_status from kernel SSE."""
    session_id = "sess-integ-1"
    run_id = "run-integ-1"
    reply_text = "ack:hello kernel"

    kernel_client = KernelApiClient(
        config=KernelApiClientConfig(base_url="http://kernel.local", token="test-token"),
        transport=_SyncTransport(session_id=session_id, run_id=run_id),
        async_transport=_AsyncSseTransport(session_id=session_id, run_id=run_id, reply_text=reply_text),
    )

    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    inbound = InboundMessage(
        channel_name="web",
        text="hello kernel",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result is not None
    assert result.agent_id == "agent-a"
    assert result.reply_text == reply_text
    assert len(channel.sent) == 1
    assert channel.sent[0].text == reply_text
