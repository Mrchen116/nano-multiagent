"""Cron and heartbeat session composition preserves configured skill scope."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.main import _KernelClientShim  # noqa: PLC2701


class _Kernel:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []

    async def create_session(self, **kwargs: Any) -> SimpleNamespace:
        self.create_calls.append(kwargs)
        return SimpleNamespace(session_id="session-a")


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
    shim = _KernelClientShim(kernel, agent_catalog=catalog)
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

