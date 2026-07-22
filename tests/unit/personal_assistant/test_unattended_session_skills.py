"""Cron and heartbeat session composition preserves configured skill scope."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.kernel_client import InProcessKernelClient


class _Kernel:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []

    async def create_session(self, **kwargs: Any) -> SimpleNamespace:
        self.create_calls.append(kwargs)
        return SimpleNamespace(session_id="session-a")

    def submit(self, **kwargs: Any) -> SimpleNamespace:
        self.submit_calls.append(kwargs)
        return SimpleNamespace(run_id="run-a")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cron", "heartbeat"])
@pytest.mark.parametrize(
    ("configured_skills", "expected_skills"),
    [
        (("restricted-a", "restricted-b"), ["restricted-a", "restricted-b"]),
        ((), None),
    ],
)
async def test_unattended_session_inherits_agent_skill_scope(
    tmp_path: Path,
    path: Literal["cron", "heartbeat"],
    configured_skills: tuple[str, ...],
    expected_skills: list[str] | None,
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                skills=configured_skills,
            ),
        )
    )
    kernel = _Kernel()
    shim = InProcessKernelClient(kernel, agent_catalog=catalog)
    metadata: dict[str, object] = {"agent_id": "agent-a"}

    if path == "cron":
        await shim.create_session(
            workspace_root=str(workspace),
            product_id="personal_assistant",
            metadata=metadata,
        )
    else:
        await shim.create_agent_session(
            agent_snapshot=catalog.require("agent-a"),
            workspace_root=str(workspace),
            product_id="personal_assistant",
            metadata=metadata,
        )

    assert kernel.create_calls[0]["skills"] == expected_skills


@pytest.mark.asyncio
async def test_unattended_session_creates_complete_runtime_when_model_resolves(
    tmp_path: Path,
) -> None:
    """Cron and heartbeat creation give Kernel one complete model-owned runtime."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                default_model="model-a",
                skills=("research",),
                tool_allowlist=("read",),
                features={"memory_curation": False},
            ),
        )
    )
    kernel = _Kernel()
    shim = InProcessKernelClient(kernel, agent_catalog=catalog)

    await shim.create_agent_session(
        agent_snapshot=catalog.require("agent-a"),
        workspace_root=str(workspace),
        product_id="personal_assistant",
        metadata={"agent_id": "agent-a"},
    )

    runtime = kernel.create_calls[0]["runtime"]
    assert runtime.model == "model-a"
    assert runtime.skills == ["research"]
    assert runtime.enabled_tools == ["read"]
    assert runtime.features == {"memory_curation": False}


@pytest.mark.asyncio
async def test_cron_runner_creates_complete_runtime_through_gateway_adapter(
    tmp_path: Path,
) -> None:
    """Cron's public runner path gives Kernel one complete isolated runtime."""
    from personal_assistant.scheduler.cron_runner import CronRunner
    from personal_assistant.scheduler.cron_scheduler import CronJob

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                default_model="model-a",
                skills=("research",),
                tool_allowlist=("read",),
                features={"memory_curation": False},
            ),
        )
    )
    kernel = _Kernel()
    runner = CronRunner(
        agent_id="agent-a",
        workspace_root=workspace,
        kernel_client=InProcessKernelClient(kernel, agent_catalog=catalog),
    )

    submitted = await runner.submit(
        job=CronJob(
            id="cron-a",
            name="Cron A",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="Check status",
        )
    )

    assert submitted == ("run-a", "session-a")
    runtime = kernel.create_calls[0]["runtime"]
    assert runtime.model == "model-a"
    assert runtime.skills == ["research"]
    assert runtime.enabled_tools == ["read"]
    assert runtime.features == {"memory_curation": False}
    assert kernel.submit_calls[0]["model"] == "model-a"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured_skills", "configured_tools", "configured_features"),
    [
        (("restricted-a",), ("read",), {"heartbeat": True}),
        ((), (), {}),
    ],
)
async def test_foreground_and_unattended_sessions_share_capability_projection(
    tmp_path: Path,
    configured_skills: tuple[str, ...],
    configured_tools: tuple[str, ...],
    configured_features: dict[str, bool],
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                skills=configured_skills,
                tool_allowlist=configured_tools,
                features=configured_features,
                custom_prompt="Keep replies concise.",
            ),
        )
    )
    snapshot = catalog.require("agent-a")
    kernel = _Kernel()
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    message = InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user-a",
        external_chat_id="conversation-a",
        is_group=False,
        agent_id="agent-a",
        metadata={"conversation_id": "conversation-a"},
    )
    await binder.resolve(
        SessionBindingRequest(
            session_key="web_relay:conversation-a:agent-a",
            reply_context=ReplyContext(
                channel_name="web_relay",
                target_chat_id="conversation-a",
            ),
            message=message,
        ),
        snapshot,
    )
    foreground = kernel.create_calls[-1]

    shim = InProcessKernelClient(kernel, agent_catalog=catalog)
    await shim.create_agent_session(
        agent_snapshot=snapshot,
        workspace_root=str(workspace),
        product_id="personal_assistant",
        metadata=foreground["metadata"],
    )
    unattended = kernel.create_calls[-1]

    assert {
        key: foreground[key]
        for key in ("prompt", "enabled_tools", "features", "skills")
    } == {
        key: unattended[key]
        for key in ("prompt", "enabled_tools", "features", "skills")
    }
