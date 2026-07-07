"""Gateway-local workspace authority helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ensure_workspace_defaults,
)


def resolve_runtime_workspace(
    *,
    agent_id: str,
    local_agents: Iterable[AgentWorkspaceConfig],
    workspace_root_factory: Callable[[str], Path],
) -> Path:
    """Resolve the Gateway runtime workspace for one agent.

    IM profile workspace values are intentionally absent from this API: they are
    display/mirror data and must not override Gateway local config.
    """

    local_agent = next(
        (agent for agent in local_agents if agent.agent_id == agent_id),
        None,
    )
    if local_agent is not None and local_agent.workspace_root is not None:
        workspace_root = local_agent.workspace_root
    else:
        workspace_root = workspace_root_factory(agent_id)
    return ensure_workspace_defaults(Path(workspace_root).expanduser().resolve())
