"""Shared helpers for GatewayRuntime lifecycle/resilience tests."""

from __future__ import annotations

import threading
from pathlib import Path

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
            models=(LLMModelPayload(name="kimiCoding:K2.6"),),
        ),
    ),
)


def make_config(tmp_path: Path) -> LocalConfig:
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


def run_in_thread(runtime: GatewayRuntime) -> tuple[threading.Thread, dict]:
    outcome: dict = {}

    def _target() -> None:
        try:
            outcome["exit_code"] = runtime.run_forever()
        except BaseException as exc:  # noqa: BLE001 — capture for assertion
            outcome["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return thread, outcome
