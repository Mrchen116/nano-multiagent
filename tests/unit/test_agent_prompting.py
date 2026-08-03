"""Consumer I/O tests for the legacy prompt-building entry points."""

from __future__ import annotations

from pathlib import Path

from agent.core.agent.prompting import (
    DEFAULT_SYSTEM_PROMPT,
    MEMORY_GUIDANCE,
    build_prompt_messages,
    build_system_prompt,
)
from agent.core.skills.registry import SkillMetadata
from agent.core.types import Message, ToolSpec

_SYSTEM_TEMPLATE = (
    "SYSTEM_INPUT_SENTINEL\n"
    "<RUNTIME_FILL:AVAILABLE_TOOLS>\n"
    "<RUNTIME_FILL:CURRENT_DATETIME>\n"
    "<RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"
)


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} description", input_schema={})


def _build_system(*tool_names: str, memory_block: str | None = None) -> str:
    return build_system_prompt(
        system_prompt=_SYSTEM_TEMPLATE,
        available_skills=(),
        available_tools=tuple(_tool(name) for name in tool_names),
        current_datetime="DATETIME_INPUT_SENTINEL",
        current_working_directory=Path("/workspace-input-sentinel"),
        memory_block=memory_block,
    )


def test_default_system_prompt_selects_segment_assembly() -> None:
    assert DEFAULT_SYSTEM_PROMPT == ""


def test_build_prompt_messages_preserves_role_order_and_runtime_inputs() -> None:
    prompts = build_prompt_messages(
        history_messages=(
            Message(message_id="history", role="assistant", content="HISTORY_SENTINEL"),
        ),
        user_text="USER_INPUT_SENTINEL",
        system_prompt=_SYSTEM_TEMPLATE,
        available_tools=(_tool("read"),),
        current_datetime="DATETIME_INPUT_SENTINEL",
        current_working_directory=Path("/workspace-input-sentinel"),
    )

    assert [item.role for item in prompts] == ["system", "assistant", "user"]
    assert "SYSTEM_INPUT_SENTINEL" in prompts[0].content
    assert "DATETIME_INPUT_SENTINEL" in prompts[0].content
    assert "/workspace-input-sentinel" in prompts[0].content
    assert "<RUNTIME_FILL:" not in prompts[0].content
    assert prompts[1].content == "HISTORY_SENTINEL"
    assert prompts[2].content == "USER_INPUT_SENTINEL"


def test_available_tools_render_names_and_descriptions_without_schemas() -> None:
    tool = ToolSpec(
        name="read",
        description="READ_DESCRIPTION_SENTINEL",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    result = build_system_prompt(
        system_prompt=_SYSTEM_TEMPLATE,
        available_skills=(),
        available_tools=(tool,),
    )

    assert "read" in result
    assert "READ_DESCRIPTION_SENTINEL" in result
    assert "input_schema" not in result
    assert '"properties"' not in result


def test_available_skills_preserve_identity_and_absolute_location() -> None:
    relative_location = Path("relative/demo/SKILL.md")
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="USER_INPUT_SENTINEL",
        available_skills=(
            SkillMetadata(
                name="demo",
                description="SKILL_DESCRIPTION_SENTINEL",
                location=relative_location,
                base_dir=relative_location.parent,
            ),
        ),
        available_tools=(_tool("skill_view"),),
    )
    system_prompt = prompts[0].content

    assert "<available_skills>" in system_prompt
    assert "<name>demo</name>" in system_prompt
    assert "SKILL_DESCRIPTION_SENTINEL" in system_prompt
    assert (
        f"<location>{relative_location.expanduser().resolve()}</location>"
        in system_prompt
    )


def test_available_skills_do_not_advertise_an_inactive_view_tool() -> None:
    location = Path("relative/demo/SKILL.md")
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="USER_INPUT_SENTINEL",
        available_skills=(
            SkillMetadata(
                name="demo",
                description="SKILL_DESCRIPTION_SENTINEL",
                location=location,
                base_dir=location.parent,
            ),
        ),
        available_tools=(_tool("read"),),
    )

    assert "<available_skills>" in prompts[0].content
    assert "skill_view" not in prompts[0].content


def test_empty_available_skills_omit_the_serialized_section() -> None:
    result = _build_system("read")

    assert "<available_skills>" not in result


def test_guidance_tracks_the_active_tool_capabilities() -> None:
    baseline = _build_system("read")
    memory = _build_system("read", "memory")
    skill_view = _build_system("read", "skill_view")
    skill_manage = _build_system("read", "skill_manage")

    assert MEMORY_GUIDANCE not in baseline
    assert MEMORY_GUIDANCE in memory
    assert skill_view != baseline
    assert "skill_view" in skill_view
    assert skill_manage != baseline
    assert "skill_manage" in skill_manage


def test_memory_block_is_injected_only_when_supplied() -> None:
    baseline = _build_system("read")
    with_memory = _build_system("read", memory_block="MEMORY_BLOCK_INPUT_SENTINEL")

    assert "MEMORY_BLOCK_INPUT_SENTINEL" not in baseline
    assert "MEMORY_BLOCK_INPUT_SENTINEL" in with_memory
