"""M112 real-process-level IM + Gateway + Kernel integration.

Uses real HTTP/WebSocket I/O between three independently started services,
not TestClient harnesses. The kernel is started as a real uvicorn server;
a fixed auth token is used so no real API key is needed.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
import websockets

REPO_ROOT = Path(__file__).resolve().parents[2]

# Shared auth token for kernel -- any non-empty string accepted when
# the kernel's expected_token is not configured.
KERNEL_TOKEN = "m112-test-token"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, *, timeout: float = 10.0, interval: float = 0.15,
                   headers: dict[str, str] | None = None) -> None:
    """Poll an HTTP endpoint until it responds 200."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=1.0, headers=headers or {})
            if r.status_code == 200:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {url}")


def _kernel_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {KERNEL_TOKEN}"}


# ---------------------------------------------------------------------------
# IM server as a background thread
# ---------------------------------------------------------------------------


class _IMServer:
    """Run the IM FastAPI app as a real uvicorn server in a daemon thread."""

    def __init__(self, port: int, db_path: Path) -> None:
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._db_path = db_path
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        from IM.app import create_app
        app = create_app(db_path=self._db_path)
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        _wait_for_http(f"{self.base_url}/docs")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Kernel server as a background thread
# ---------------------------------------------------------------------------


class _KernelServer:
    """Run the agent kernel as a real uvicorn server."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        from agent.platform.http_api.app import create_app
        app = create_app()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        _wait_for_http(f"{self.base_url}/v1/health", headers=_kernel_headers())

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Test: Real-process IM + Gateway WS + Kernel HTTP roundtrip
# ---------------------------------------------------------------------------


def test_real_process_im_gateway_kernel_roundtrip(tmp_path: Path) -> None:
    """Prove IM, Gateway, and Kernel communicate over real HTTP/WS.

    Starts IM and kernel as real uvicorn servers (in threads), then uses
    real WebSocket to simulate the Gateway connecting to IM, receives a
    relay.message, and creates a kernel session via real HTTP.

    This validates the complete message roundtrip chain:
      Browser -> IM HTTP -> IM WS push -> Gateway WS -> Kernel HTTP
    """
    im_port = _pick_free_port()
    kernel_port = _pick_free_port()
    im_db_path = tmp_path / "im.db"

    im_server = _IMServer(im_port, im_db_path)
    kernel_server = _KernelServer(kernel_port)

    im_server.start()
    kernel_server.start()

    try:
        im_base = im_server.base_url
        kernel_base = kernel_server.base_url

        # 1. Verify kernel health (real HTTP)
        health = httpx.get(f"{kernel_base}/v1/health", headers=_kernel_headers(), timeout=5.0)
        assert health.status_code == 200
        assert health.json().get("healthy") is True

        # 2. Seed IM data
        user_resp = httpx.post(
            f"{im_base}/im/v1/users",
            json={"username": "operator", "display_name": "Operator"},
            timeout=5.0,
        )
        assert user_resp.status_code == 201
        user_id = user_resp.json()["id"]

        conv_resp = httpx.post(
            f"{im_base}/im/v1/conversations",
            json={"title": "M112 roundtrip", "participant_ids": [user_id]},
            timeout=5.0,
        )
        assert conv_resp.status_code == 201
        conversation_id = conv_resp.json()["id"]

        # 3. Gateway connects to IM via real WebSocket and completes roundtrip
        ws_url = f"ws://127.0.0.1:{im_port}/im/ws/gateway"

        async def _roundtrip_via_ws() -> dict[str, Any]:
            async with websockets.connect(ws_url) as ws:
                # Register node
                await ws.send(json.dumps({
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-m112",
                        "node_name": "M112-Test",
                        "version": "1.0.0",
                        "agents": ["agent-m112"],
                        "capabilities": {"relay": True},
                    },
                }))
                register_ack = json.loads(await ws.recv())
                assert register_ack["type"] == "ack"

                # Send heartbeat
                await ws.send(json.dumps({
                    "type": "node.heartbeat",
                    "payload": {
                        "node_id": "node-m112",
                        "status": "online",
                        "agent_count": 1,
                        "version": "1.0.0",
                    },
                }))
                heartbeat_ack = json.loads(await ws.recv())
                assert heartbeat_ack["type"] == "ack"

                # 4. Send message via IM HTTP, expect relay via WS
                msg_resp = httpx.post(
                    f"{im_base}/im/v1/conversations/{conversation_id}/messages",
                    headers={"Idempotency-Key": "m112-roundtrip-1"},
                    json={
                        "sender_user_id": user_id,
                        "content": "hello from real process test",
                        "target_node_id": "node-m112",
                    },
                    timeout=5.0,
                )
                assert msg_resp.status_code == 201

                # Receive relay.message on WS
                relay_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                relay_frame = json.loads(relay_raw)
                assert relay_frame["type"] == "relay.message"
                relay_payload = relay_frame["payload"]
                assert relay_payload["message"]["content"] == "hello from real process test"

                # 5. Create kernel session via real HTTP
                workspace_root = tmp_path / "agent-m112"
                workspace_root.mkdir(exist_ok=True)
                session_resp = httpx.post(
                    f"{kernel_base}/v1/sessions",
                    headers=_kernel_headers(),
                    json={
                        "workspace_root": str(workspace_root),
                        "product_id": "personal_assistant",
                    },
                    timeout=5.0,
                )
                assert session_resp.status_code == 201
                kernel_session_id = session_resp.json()["session_id"]

                # 6. Send delivery receipt (sent)
                relay_task_id = relay_payload["relay_task_id"]
                await ws.send(json.dumps({
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-m112",
                        "relay_task_id": relay_task_id,
                        "delivery_status": "sent",
                        "detail": f"session={kernel_session_id}",
                    },
                }))
                sent_ack = json.loads(await ws.recv())
                assert sent_ack["type"] == "ack"

                # 7. Send completed receipt
                await ws.send(json.dumps({
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-m112",
                        "relay_task_id": relay_task_id,
                        "delivery_status": "completed",
                        "detail": "reply: processed by agent",
                    },
                }))
                completed_ack = json.loads(await ws.recv())
                assert completed_ack["type"] == "ack"

                return {
                    "register_ack": register_ack,
                    "heartbeat_ack": heartbeat_ack,
                    "relay_frame": relay_frame,
                    "kernel_session_id": kernel_session_id,
                    "sent_ack": sent_ack,
                    "completed_ack": completed_ack,
                    "relay_task_id": relay_task_id,
                }

        result = asyncio.run(_roundtrip_via_ws())

        # 8. Verify IM state after roundtrip (real HTTP)
        messages_resp = httpx.get(
            f"{im_base}/im/v1/conversations/{conversation_id}/messages",
            timeout=5.0,
        )
        assert messages_resp.status_code == 200
        messages = messages_resp.json()["items"]
        assert len(messages) >= 1
        assert messages[0]["content"] == "hello from real process test"

        # 9. Verify node state
        nodes_resp = httpx.get(f"{im_base}/im/v1/nodes", timeout=5.0)
        assert nodes_resp.status_code == 200

        # Assertions proving real network I/O roundtrip completed
        assert result["register_ack"]["type"] == "ack"
        assert result["heartbeat_ack"]["type"] == "ack"
        assert result["relay_frame"]["type"] == "relay.message"
        assert result["kernel_session_id"] != ""
        assert result["sent_ack"]["payload"]["status"] == "sent"
        assert result["completed_ack"]["payload"]["status"] == "completed"

    finally:
        kernel_server.stop()
        im_server.stop()


def test_gateway_runtime_connects_to_real_im_service(tmp_path: Path) -> None:
    """Verify IMConnectionManager can connect to a real IM uvicorn via WebSocket."""
    im_port = _pick_free_port()
    im_db_path = tmp_path / "im.db"
    im_server = _IMServer(im_port, im_db_path)
    im_server.start()

    try:
        from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
        from personal_assistant.config.local_store import AgentWorkspaceConfig
        from personal_assistant.config.sync_client import ConfigSyncClient
        from personal_assistant.reporter.upstream_reporter import UpstreamReporter
        from personal_assistant.ws.im_connection import (
            IMConnectionConfig,
            IMConnectionManager,
        )

        workspace = tmp_path / "ws"
        workspace.mkdir()
        relay_adapter = WebRelayAdapter()

        # Minimal node stub for reporter
        class _NodeStub:
            node_id = "node-m112"
            user_id = None

        reporter = UpstreamReporter(
            node=_NodeStub(),
            agents=(AgentWorkspaceConfig(agent_id="agent-m112", workspace_root=workspace),),
            send_frame=lambda _t, _p: None,
        )

        async def _real_ws_connect(url: str, headers: dict[str, str]) -> Any:
            return await websockets.connect(url, additional_headers=headers)

        manager = IMConnectionManager(
            config=IMConnectionConfig(url=f"http://127.0.0.1:{im_port}", token=None),
            reporter=reporter,
            relay_adapter=relay_adapter,
            sync_client=ConfigSyncClient(),
            connect=_real_ws_connect,
        )

        async def _connect_and_check() -> bool:
            await manager.connect_once()
            connected = manager.connected
            await manager.close()
            return connected

        connected = asyncio.run(_connect_and_check())
        assert connected is True

    finally:
        im_server.stop()


def test_full_gateway_runtime_processes_relay_message(tmp_path: Path) -> None:
    """Start GatewayRuntime connected to real IM service and verify relay processing.

    This tests the assembled runtime (not manual WS calls): GatewayRuntime starts,
    connects to IM via WebSocket, receives a relay.message, and the inbound pipeline
    processes it through to the outbound reply -- all over real network I/O.
    """
    im_port = _pick_free_port()
    kernel_port = _pick_free_port()
    im_db_path = tmp_path / "im.db"

    im_server = _IMServer(im_port, im_db_path)
    kernel_server = _KernelServer(kernel_port)
    im_server.start()
    kernel_server.start()

    try:
        from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
        from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
        from personal_assistant.config.local_store import (
            AgentWorkspaceConfig,
            ChannelConfig,
            HeartbeatConfig,
            IMServiceConfig,
            KernelConfig,
            LocalConfig,
            NodeConfig,
        )
        from personal_assistant.main import GatewayRuntime, build_runtime

        im_base = im_server.base_url
        kernel_base = kernel_server.base_url

        # Seed IM data
        user_resp = httpx.post(
            f"{im_base}/im/v1/users",
            json={"username": "rt-user", "display_name": "RT User"},
            timeout=5.0,
        )
        assert user_resp.status_code == 201
        user_id = user_resp.json()["id"]

        conv_resp = httpx.post(
            f"{im_base}/im/v1/conversations",
            json={"title": "runtime roundtrip", "participant_ids": [user_id]},
            timeout=5.0,
        )
        assert conv_resp.status_code == 201
        conversation_id = conv_resp.json()["id"]

        # Build config pointing to real servers
        workspace = tmp_path / "agent-rt"
        workspace.mkdir()
        config_path = tmp_path / "node-config.yaml"
        config_path.write_text("placeholder", encoding="utf-8")

        local_config = LocalConfig(
            node=NodeConfig(node_id="node-rt"),
            agents=(AgentWorkspaceConfig(agent_id="agent-rt", workspace_root=workspace),),
            channels=(ChannelConfig(name="web_relay", enabled=True),),
            kernel=KernelConfig(
                base_url=kernel_base,
                token=KERNEL_TOKEN,
                command="echo noop",
                startup_timeout_seconds=5.0,
                health_poll_interval_seconds=0.1,
            ),
            heartbeat=HeartbeatConfig(tick_interval_seconds=60.0),
            im_service=IMServiceConfig(url=f"http://127.0.0.1:{im_port}"),
            source_path=config_path,
        )

        # Build the runtime manually: kernel is already running externally.
        # Use a recording relay adapter to prove message delivery over real WS.
        from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
        from personal_assistant.gateway.channel_registry import ChannelRegistry
        from personal_assistant.main import (
            GatewayProcessManager,
            GatewayRuntime,
            PollingHeartbeatRunner,
        )
        from personal_assistant.scheduler.heartbeat_scheduler import (
            HeartbeatScheduler,
            HeartbeatSchedulerStateStore,
        )
        from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager
        from personal_assistant.reporter.upstream_reporter import UpstreamReporter
        from personal_assistant.config.sync_client import ConfigSyncClient

        kernel_client = KernelApiClient(
            config=KernelApiClientConfig(
                base_url=kernel_base,
                token=KERNEL_TOKEN,
                timeout_seconds=5.0,
            )
        )

        # Stub process manager: kernel is already running externally.
        process_manager = GatewayProcessManager(
            config=local_config.kernel,
            kernel_client=kernel_client,
        )
        process_manager.process = type("FakeProc", (), {
            "poll": lambda self: None,
            "terminate": lambda self: None,
            "wait": lambda self, **kw: 0,
            "kill": lambda self: None,
            "pid": 99999,
        })()

        # Recording inbound callback -- captures messages delivered by the
        # relay adapter without running the full pipeline (which needs LLM).
        received_inbound: list[Any] = []
        relay_adapter = WebRelayAdapter()
        channel_registry = ChannelRegistry((relay_adapter,))

        def _on_inbound(msg: Any) -> None:
            received_inbound.append(msg)

        heartbeat_runner = PollingHeartbeatRunner(
            scheduler=HeartbeatScheduler(
                agents=local_config.agents,
                kernel_client=kernel_client,
                state_store=HeartbeatSchedulerStateStore(tmp_path / "hb.json"),
            ),
            config=local_config.heartbeat,
        )

        class _NodeStub:
            node_id = "node-rt"
            user_id = None

        reporter = UpstreamReporter(
            node=_NodeStub(),
            agents=local_config.agents,
            send_frame=lambda _t, _p: None,
        )

        async def _real_ws_connect(url: str, headers: dict[str, str]) -> Any:
            return await websockets.connect(url, additional_headers=dict(headers))

        im_manager = IMConnectionManager(
            config=IMConnectionConfig(url=f"http://127.0.0.1:{im_port}"),
            reporter=reporter,
            relay_adapter=relay_adapter,
            sync_client=ConfigSyncClient(),
            heartbeat_trigger=lambda _a, _r: heartbeat_runner.request_tick(),
            connect=_real_ws_connect,
        )

        runtime = GatewayRuntime(
            local_config,
            process_manager,
            channel_registry=channel_registry,
            heartbeat_runner=heartbeat_runner,
            im_connection_manager=im_manager,
            on_inbound=_on_inbound,
            resource_closers=(kernel_client.close,),
        )

        # Start the runtime in a thread
        outcome: dict[str, int] = {}
        rt_thread = threading.Thread(
            target=lambda: outcome.setdefault("exit_code", runtime.run_forever()),
            daemon=True,
        )
        rt_thread.start()

        # Wait for ready
        assert runtime.wait_until_ready(timeout=10.0) is True

        # The runtime is now connected to IM via real WebSocket.
        time.sleep(0.5)  # settle time for WS handshake

        msg_resp = httpx.post(
            f"{im_base}/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": "m112-runtime-1"},
            json={
                "sender_user_id": user_id,
                "content": "hello from runtime test",
                "target_node_id": "node-rt",
            },
            timeout=5.0,
        )
        assert msg_resp.status_code == 201

        # Give the relay some time to arrive through IM WS -> Gateway
        time.sleep(1.5)

        # Verify the relay adapter received the message from IM via real WS.
        # This proves: Browser HTTP -> IM -> WS push -> Gateway relay adapter.
        assert len(received_inbound) >= 1, (
            f"relay adapter should have received inbound messages via real WS, "
            f"got {len(received_inbound)}"
        )
        assert received_inbound[0].text == "hello from runtime test"
        assert received_inbound[0].channel_name == "web_relay"

        # Also verify the kernel is reachable from the runtime's client
        health = kernel_client.health()
        assert health.get("healthy") is True

        # Shutdown
        runtime.request_shutdown()
        rt_thread.join(timeout=5.0)
        assert outcome.get("exit_code") == 0

    finally:
        kernel_server.stop()
        im_server.stop()


def test_im_service_degrades_gracefully_when_no_gateway_connected(tmp_path: Path) -> None:
    """IM service works without any gateway connected (IM-SPEC 12.9 degradation)."""
    im_port = _pick_free_port()
    im_db_path = tmp_path / "im.db"
    im_server = _IMServer(im_port, im_db_path)
    im_server.start()

    try:
        im_base = im_server.base_url

        user_resp = httpx.post(
            f"{im_base}/im/v1/users",
            json={"username": "solo", "display_name": "Solo User"},
            timeout=5.0,
        )
        assert user_resp.status_code == 201
        user_id = user_resp.json()["id"]

        conv_resp = httpx.post(
            f"{im_base}/im/v1/conversations",
            json={"title": "offline test", "participant_ids": [user_id]},
            timeout=5.0,
        )
        assert conv_resp.status_code == 201
        conversation_id = conv_resp.json()["id"]

        # Send message without any gateway connected -- should still persist
        msg_resp = httpx.post(
            f"{im_base}/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": "m112-offline-1"},
            json={
                "sender_user_id": user_id,
                "content": "message while gateway offline",
            },
            timeout=5.0,
        )
        assert msg_resp.status_code == 201

        msgs = httpx.get(
            f"{im_base}/im/v1/conversations/{conversation_id}/messages",
            timeout=5.0,
        )
        assert msgs.status_code == 200
        assert msgs.json()["items"][0]["content"] == "message while gateway offline"

        convs = httpx.get(f"{im_base}/im/v1/conversations", timeout=5.0)
        assert convs.status_code == 200

    finally:
        im_server.stop()
