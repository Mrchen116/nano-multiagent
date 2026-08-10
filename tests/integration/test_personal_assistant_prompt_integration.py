"""Integration coverage for PA prompt slots assembled by the kernel template."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.skeleton import build_kernel_prompt_skeleton
from agent.core.types import ToolSpec
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.product import prompt_for


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} tool", input_schema={})


def _assemble(
    agent: Any,
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


def test_legacy_system_input_is_ignored_and_custom_is_injected_once(
    tmp_path: Path,
) -> None:
    """Only the public canonical custom field may shape the PA prompt."""
    legacy = "LEGACY-SYSTEM-SENTINEL-UNIQUE"
    custom = "CUSTOM-SENTINEL-UNIQUE"
    agent = SimpleNamespace(
        agent_id="agent-a",
        workspace_root=tmp_path,
        system_prompt=legacy,
        custom_prompt=custom,
    )

    prompt = _assemble(agent)

    assert legacy not in prompt
    assert prompt.count(custom) == 1


def test_footer_policy_false_omits_datetime_but_keeps_cwd_for_arbitrary_prompt_name(
    tmp_path: Path,
) -> None:
    from agent.sdk import PromptSlots, PromptText

    prompt = assemble_system_prompt(
        build_kernel_prompt_skeleton(),
        PromptContext(
            current_datetime="2026-08-10T09:17:00+08:00",
            cwd=str(tmp_path),
            flags={"include_session_created_datetime": False},
            prompt_slots=PromptSlots(
                head=(
                    PromptText(name="not.pa.anything", text="Time zone: Asia/Shanghai"),
                )
            ),
        ),
    )

    assert "Time zone: Asia/Shanghai" in prompt
    assert "Current date and time:" not in prompt
    assert f"Current working directory: {tmp_path}" in prompt


def test_omitted_footer_policy_is_byte_identical_to_explicit_true(
    tmp_path: Path,
) -> None:
    omitted = assemble_system_prompt(
        build_kernel_prompt_skeleton(),
        PromptContext(current_datetime="created", cwd=str(tmp_path)),
    )
    explicit = assemble_system_prompt(
        build_kernel_prompt_skeleton(),
        PromptContext(
            current_datetime="created",
            cwd=str(tmp_path),
            flags={"include_session_created_datetime": True},
        ),
    )

    assert omitted == explicit
