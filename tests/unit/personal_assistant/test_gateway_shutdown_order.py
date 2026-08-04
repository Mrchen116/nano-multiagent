"""Kernel shutdown ownership regression test."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    IMServiceConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.runtime import GatewayRuntime

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(
                    name="kimiCoding:K2.6",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
            ),
        ),
    ),
)


class _FakeIMManager:
    def __init__(self) -> None:
        self._closed = asyncio.Event()
        self.connected = True

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        del timeout

    async def close(self) -> None:
        self.connected = False
        self._closed.set()


class _FakeKernel:
    def __init__(self) -> None:
        self.aclose_calls = 0
        self.close_calls = 0

    async def aclose(self) -> None:
        self.aclose_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _make_config(tmp_path: Path) -> LocalConfig:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir(exist_ok=True)
    return LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )


def test_gateway_runtime_closes_kernel_once_via_async_owner(tmp_path: Path) -> None:
    """One Gateway shutdown closes the Kernel exactly once through ``aclose``."""
    kernel = _FakeKernel()
    runtime = GatewayRuntime(
        _make_config(tmp_path),
        kernel=kernel,
        im_connection_manager=_FakeIMManager(),
    )

    def _shutdown_after_ready() -> None:
        runtime.wait_until_ready(timeout=5.0)
        runtime.request_shutdown()

    thread = threading.Thread(target=_shutdown_after_ready, daemon=True)
    thread.start()
    runtime.run_forever()
    thread.join(timeout=5.0)

    assert kernel.aclose_calls == 1
    assert kernel.close_calls == 0
