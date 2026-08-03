"""Integration coverage for PA prompt slots assembled by the kernel template."""

from __future__ import annotations

from pathlib import Path

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.skeleton import build_kernel_prompt_skeleton
from agent.core.types import ToolSpec
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.product import prompt_for


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} tool", input_schema={})


def _assemble(
    agent: AgentWorkspaceConfig,
    *,
    tools: tuple[ToolSpec, ...] = (),
    scenario: dict[str, object] | None = None,
) -> str:
    prompt_scenario = scenario or {}
    context = PromptContext(
        available_tools=tools,
        current_datetime="2026-01-01T00:00:00",
        cwd=str(agent.workspace_root),
        scenario=prompt_scenario,
        prompt_slots=prompt_for(agent, scenario=prompt_scenario),
    )
    return assemble_system_prompt(build_kernel_prompt_skeleton(), context)


def test_group_scenario_reaches_the_assembled_pa_prompt(tmp_path: Path) -> None:
    """Preserve typed participant identities through product and kernel seams."""
    agent = AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path)
    prompt = _assemble(
        agent,
        tools=(_tool("memory"), _tool("skill_manage"), _tool("agent")),
        scenario={
            "conversation_type": "group",
            "agent_id": "agent-a",
            "participants": [
                {
                    "type": "agent",
                    "agent_id": "agent-peer-unique",
                    "display_name": "Peer",
                },
                {
                    "type": "user",
                    "user_id": "user-unique",
                    "display_name": "Alice",
                },
            ],
        },
    )

    assert "agent-peer-unique" in prompt
    assert "user-unique" in prompt
    assert '<mention type="agent" target_id="<id>"/>' in prompt
    assert "<task-notification>" in prompt


def test_system_and_custom_inputs_keep_their_product_order(tmp_path: Path) -> None:
    """Keep both configured inputs visible without pinning surrounding prose."""
    system = "SYSTEM-SENTINEL-UNIQUE"
    custom = "CUSTOM-SENTINEL-UNIQUE"
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=tmp_path,
        system_prompt=system,
        custom_prompt=custom,
    )

    prompt = _assemble(agent)

    assert prompt.index(system) < prompt.index(custom)
