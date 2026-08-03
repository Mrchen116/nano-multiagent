"""Consumer-path protection for workspace instruction prompt input."""

from __future__ import annotations

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    RenderMode,
    assemble_system_prompt,
)
from agent.core.agent.prompt_sections.skeleton import build_kernel_prompt_skeleton


def _assemble(ctx: PromptContext) -> str:
    return assemble_system_prompt(build_kernel_prompt_skeleton(), ctx)


def test_runtime_prompt_preserves_workspace_instruction_input() -> None:
    prompt = _assemble(
        PromptContext(
            agents_md_content="AGENTS_MD_INPUT_SENTINEL",
            render_mode=RenderMode.RUNTIME,
        )
    )

    assert "AGENTS_MD_INPUT_SENTINEL" in prompt


def test_runtime_prompt_omits_missing_workspace_instruction_input() -> None:
    prompt = _assemble(PromptContext(render_mode=RenderMode.RUNTIME))

    assert "AGENTS_MD_INPUT_SENTINEL" not in prompt


def test_preview_exposes_workspace_instruction_slot_without_runtime_value() -> None:
    prompt = _assemble(PromptContext(render_mode=RenderMode.PREVIEW))

    assert prompt
    assert "AGENTS_MD_INPUT_SENTINEL" not in prompt
