"""Persistent-session and live-dispatch endpoint restart integration."""

from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, PermissionDecision, build_kernel

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.internal_dispatch import InternalDispatchEndpoint
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
from personal_assistant.tools.send_message import SendMessageTool


class _RecordingListener:
    """Own one real loopback HTTP listener and record JSON dispatches."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        sink = self.requests

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length))
                sink.append(payload)
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


class _SendMessageThenStopLLM:
    """Issue one real send_message tool call, then finish the run."""

    def __init__(self) -> None:
        self.requests: list[Any] = []

    def generate(self, request: Any):
        self.requests.append(request)
        first = len(self.requests) == 1

        async def _stream():
            if first:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call-restart-dispatch",
                            name="send_message",
                            arguments={"text": "after restart", "to": "agent-b"},
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
            else:
                yield LLMMessage(role="assistant", content="done")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


async def _allow_all(_tool: str, _input: Any, _ctx: Any) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


def _build_kernel(
    *, repo_root: Path, endpoint: InternalDispatchEndpoint, llm_client: Any
):
    return build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        tools=(
            SendMessageTool(
                gateway_dispatch_url_provider=endpoint.current_url,
            ),
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=repo_root,
        _llm_client_override=llm_client,
    )


def _binding_request(*, dispatch_url: str) -> SessionBindingRequest:
    message = InboundMessage(
        channel_name="web_relay",
        text="continue",
        external_user_id="user-a",
        external_chat_id="conversation-a",
        is_group=False,
        agent_id="agent-a",
        metadata={"conversation_id": "conversation-a"},
    )
    return SessionBindingRequest(
        session_key="web_relay:conversation-a:agent-a",
        reply_context=ReplyContext(
            channel_name="web_relay", target_chat_id="conversation-a"
        ),
        message=message,
        gateway_dispatch_url=dispatch_url,
    )


async def _wait_terminal(kernel: Any, run_id: str) -> str:
    while True:
        status = str(kernel.get_run(run_id).status)
        if status in {"completed", "failed", "cancelled"}:
            return status
        await asyncio.sleep(0.01)


async def test_restart_reuses_session_history_but_dispatches_only_to_new_listener(
    tmp_path: Path,
) -> None:
    """A→B restart keeps durable history while the real tool uses only live B."""

    listener_a = _RecordingListener()
    listener_b = _RecordingListener()
    endpoint_a = InternalDispatchEndpoint()
    endpoint_b = InternalDispatchEndpoint()
    url_a = endpoint_a.publish(host="127.0.0.1", port=listener_a.port)
    url_b = endpoint_b.publish(host="127.0.0.1", port=listener_b.port)
    workspace = tmp_path / "agent-workspace"
    workspace.mkdir()
    repo_root = tmp_path / "kernel-root"
    repo_root.mkdir()
    binding_db = tmp_path / "session-bindings.sqlite3"
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        tool_allowlist=("send_message",),
    )
    sentinel = "HISTORY-BEFORE-RESTART"
    kernel_a = _build_kernel(
        repo_root=repo_root, endpoint=endpoint_a, llm_client=_SendMessageThenStopLLM()
    )
    try:
        catalog_a = LiveAgentCatalog((agent,))
        binder_a = GatewaySessionBinder(
            catalog=catalog_a,
            repository=PersistentSessionBindingStore(db_path=binding_db),
            kernel=kernel_a,
        )
        binding_a = await binder_a.resolve(
            _binding_request(dispatch_url=url_a), catalog_a.require("agent-a")
        )
        kernel_a.append_message(
            binding_a.kernel_session_id,
            role="user",
            content=sentinel,
            workspace_root=workspace,
        )
    finally:
        await kernel_a.aclose()

    llm_b = _SendMessageThenStopLLM()
    kernel_b = _build_kernel(repo_root=repo_root, endpoint=endpoint_b, llm_client=llm_b)
    try:
        catalog_b = LiveAgentCatalog((agent,))
        store_b = PersistentSessionBindingStore(db_path=binding_db)
        binder_b = GatewaySessionBinder(
            catalog=catalog_b,
            repository=store_b,
            kernel=kernel_b,
        )
        binding_b = await binder_b.resolve(
            _binding_request(dispatch_url=url_b), catalog_b.require("agent-a")
        )

        assert binding_b.kernel_session_id == binding_a.kernel_session_id
        reopened = kernel_b.get_session(
            binding_b.kernel_session_id, workspace_root=workspace
        )
        assert reopened["metadata"]["gateway_dispatch_url"] == url_a

        run = kernel_b.submit(
            session_id=binding_b.kernel_session_id,
            parts=[{"type": "text", "text": "dispatch after restart"}],
            workspace_root=workspace,
        )
        assert await _wait_terminal(kernel_b, run.run_id) == "completed"

        assert listener_a.requests == []
        assert [request["text"] for request in listener_b.requests] == [
            "after restart"
        ]
        assert any(
            sentinel in str(message.content)
            for message in llm_b.requests[0].messages
        )
        persisted = store_b.get(binding_b.session_key)
        assert persisted is not None
        assert persisted.kernel_session_id == binding_a.kernel_session_id
    finally:
        await kernel_b.aclose()
        listener_a.close()
        listener_b.close()
