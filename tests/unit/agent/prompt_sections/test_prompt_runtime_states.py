"""Runtime/preview behavior for volatile core prompt inputs."""

from __future__ import annotations

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    RenderMode,
    assemble_system_prompt,
)
from agent.core.agent.prompt_sections.core_sections import (
    CORE_MEMORY_BLOCK,
    CORE_USER_PROFILE_BLOCK,
)

_VOLATILE_SECTIONS = (CORE_MEMORY_BLOCK, CORE_USER_PROFILE_BLOCK)


def test_runtime_prompt_preserves_memory_and_user_profile_inputs() -> None:
    prompt = assemble_system_prompt(
        _VOLATILE_SECTIONS,
        PromptContext(
            memory_content="MEMORY_INPUT_SENTINEL",
            user_profile_content="USER_PROFILE_INPUT_SENTINEL",
            render_mode=RenderMode.RUNTIME,
        ),
    )

    assert "MEMORY_INPUT_SENTINEL" in prompt
    assert "USER_PROFILE_INPUT_SENTINEL" in prompt


def test_runtime_prompt_omits_empty_volatile_inputs() -> None:
    prompt = assemble_system_prompt(
        _VOLATILE_SECTIONS,
        PromptContext(render_mode=RenderMode.RUNTIME),
    )

    assert prompt == ""


def test_preview_exposes_volatile_slots_without_runtime_values() -> None:
    prompt = assemble_system_prompt(
        _VOLATILE_SECTIONS,
        PromptContext(render_mode=RenderMode.PREVIEW),
    )

    assert prompt
    assert "MEMORY_INPUT_SENTINEL" not in prompt
    assert "USER_PROFILE_INPUT_SENTINEL" not in prompt
