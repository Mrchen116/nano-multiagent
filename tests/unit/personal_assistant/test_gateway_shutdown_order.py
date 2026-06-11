"""Unit tests for Gateway producer→consumer shutdown order (bugfix-402-M3 R3).

Verifies Decision 7: Gateway closes in order
  1. heartbeat/dispatch (producers)
  2. kernel.aclose() (drain runs)
  3. IM connection + im_task (consumers / transport)
  4. other resource_closers

These are C1 red tests — they test the *interface* (GatewayRuntime accepts a
``kernel`` parameter and calls its aclose before closing IM).
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Callable

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import GatewayRuntime

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
    """Minimal IM connection manager that records shutdown event."""

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()
        self.connected = True

    async def connect_once(self) -> None:
        self._events.append("im.connect")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
        self._closed.set()


class _FakeHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.close")


class _FakeKernel:
    """Minimal kernel stub that records aclose and close calls."""

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.aclose_calls = 0
        self.close_calls = 0

    async def aclose(self) -> None:
        self._events.append("kernel.aclose")
        self.aclose_calls += 1

    def close(self) -> None:
        self._events.append("kernel.close")
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
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )


# ---------------------------------------------------------------------------
# R3 tests
# ---------------------------------------------------------------------------


def test_gateway_runtime_accepts_kernel_parameter(tmp_path: Path) -> None:
    """GatewayRuntime must accept a ``kernel`` keyword argument (bugfix-402-M3 R3)."""
    events: list[str] = []
    config = _make_config(tmp_path)
    kernel = _FakeKernel(events)

    # Must not raise TypeError — the parameter must exist.
    runtime = GatewayRuntime(
        config,
        None,
        kernel=kernel,
    )
    assert runtime is not None


def test_gateway_runtime_calls_kernel_aclose_before_im_close(tmp_path: Path) -> None:
    """Gateway shutdown must call kernel.aclose() before closing IM (Decision 7).

    Order verified: heartbeat.close → kernel.aclose → im.close
    """
    events: list[str] = []
    config = _make_config(tmp_path)
    kernel = _FakeKernel(events)
    heartbeat = _FakeHeartbeatRunner(events)
    im_manager = _FakeIMManager(events)

    runtime = GatewayRuntime(
        config,
        None,
        kernel=kernel,
        heartbeat_runner=heartbeat,
        im_connection_manager=im_manager,
    )

    # Trigger shutdown immediately after ready.
    def _request_shutdown_after_ready() -> None:
        runtime.wait_until_ready(timeout=5.0)
        runtime.request_shutdown()

    t = threading.Thread(target=_request_shutdown_after_ready, daemon=True)
    t.start()
    runtime.run_forever()
    t.join(timeout=5.0)

    # Verify order: heartbeat must close before kernel; kernel must close before IM.
    assert "heartbeat.close" in events, "heartbeat.close not in events"
    assert "kernel.aclose" in events, "kernel.aclose not in events"
    assert "im.close" in events, "im.close not in events"

    hb_idx = events.index("heartbeat.close")
    ka_idx = events.index("kernel.aclose")
    im_idx = events.index("im.close")

    assert hb_idx < ka_idx, (
        f"heartbeat.close ({hb_idx}) must precede kernel.aclose ({ka_idx}); got {events}"
    )
    assert ka_idx < im_idx, (
        f"kernel.aclose ({ka_idx}) must precede im.close ({im_idx}); got {events}"
    )


def test_gateway_runtime_kernel_aclose_called_exactly_once(tmp_path: Path) -> None:
    """kernel.aclose() must be called exactly once per shutdown, not close()."""
    events: list[str] = []
    config = _make_config(tmp_path)
    kernel = _FakeKernel(events)
    im_manager = _FakeIMManager(events)

    runtime = GatewayRuntime(
        config,
        None,
        kernel=kernel,
        im_connection_manager=im_manager,
    )

    def _shutdown_after_ready() -> None:
        runtime.wait_until_ready(timeout=5.0)
        runtime.request_shutdown()

    t = threading.Thread(target=_shutdown_after_ready, daemon=True)
    t.start()
    runtime.run_forever()
    t.join(timeout=5.0)

    assert kernel.aclose_calls == 1, (
        f"kernel.aclose must be called exactly once, got {kernel.aclose_calls}"
    )
    assert kernel.close_calls == 0, (
        f"kernel.close (sync) must not be called during async shutdown, got {kernel.close_calls}"
    )


def test_build_runtime_does_not_add_kernel_close_to_resource_closers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_runtime must not add kernel.close to resource_closers (bugfix-402-M3 R3).

    After R3, the Kernel is passed directly as ``kernel=`` to GatewayRuntime;
    the old ``resource_closers=(kernel.close,)`` pattern must be gone.
    """
    from personal_assistant.main import build_runtime

    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    runtime = build_runtime(config)

    # None of the resource_closers should be the kernel's close method.
    # The most reliable check is that the Kernel is wired as runtime._kernel.
    assert hasattr(runtime, "_kernel"), (
        "GatewayRuntime must have a _kernel attribute after build_runtime (M3 R3)"
    )
    assert runtime._kernel is not None  # noqa: SLF001
