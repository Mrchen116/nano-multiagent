"""feat-428-M1 R2: 机制 A — CORE_AGENTS_MD_BLOCK 段渲染 + skeleton 段位 + wiring 透传.

机制 A 把 agent 工作区根 AGENTS.md 注入 system prompt：
- PromptContext.agents_md_content 载体字段。
- CORE_AGENTS_MD_BLOCK 段 cache_safe=True，三态渲染（PREVIEW 占位 / RUNTIME 有内容 / RUNTIME 空 → None）。
- skeleton 插在 _SLOT_CUSTOM 之后、CORE_MEMORY_BLOCK 之前（仍在稳定前缀末尾，满足 cache_safe 不变量）。
- wiring.build_prompt_context_from_metadata 透传 agents_md_content。

这些测试在 R2 实施之前是红的。
"""

from __future__ import annotations

import dataclasses

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    RenderMode,
    assemble_system_prompt,
)


# ---------------------------------------------------------------------------
# PromptContext 字段
# ---------------------------------------------------------------------------


def test_prompt_context_has_agents_md_content_field() -> None:
    fields = {f.name for f in dataclasses.fields(PromptContext)}
    assert "agents_md_content" in fields


# ---------------------------------------------------------------------------
# CORE_AGENTS_MD_BLOCK 段三态渲染
# ---------------------------------------------------------------------------


def test_agents_md_block_runtime_renders_content() -> None:
    from agent.core.agent.prompt_sections.core_sections import CORE_AGENTS_MD_BLOCK

    ctx = PromptContext(
        agents_md_content="follow the local conventions",
        render_mode=RenderMode.RUNTIME,
    )
    assert CORE_AGENTS_MD_BLOCK.enabled_when(ctx) is True
    rendered = CORE_AGENTS_MD_BLOCK.render(ctx)
    assert rendered is not None
    assert "follow the local conventions" in rendered
    # design 注入文案：用 <project-instructions> 标签包裹。
    assert "<project-instructions" in rendered
    assert "</project-instructions>" in rendered


def test_agents_md_block_runtime_empty_returns_none() -> None:
    from agent.core.agent.prompt_sections.core_sections import CORE_AGENTS_MD_BLOCK

    ctx = PromptContext(agents_md_content=None, render_mode=RenderMode.RUNTIME)
    assert CORE_AGENTS_MD_BLOCK.enabled_when(ctx) is False
    assert CORE_AGENTS_MD_BLOCK.render(ctx) is None


def test_agents_md_block_preview_renders_placeholder() -> None:
    from agent.core.agent.prompt_sections.core_sections import CORE_AGENTS_MD_BLOCK

    ctx = PromptContext(agents_md_content=None, render_mode=RenderMode.PREVIEW)
    # PREVIEW 恒 True，输出占位（对齐 _render_memory_block）。
    assert CORE_AGENTS_MD_BLOCK.enabled_when(ctx) is True
    rendered = CORE_AGENTS_MD_BLOCK.render(ctx)
    assert rendered is not None
    assert "<运行时注入：工作区 AGENTS.md>" in rendered


def test_agents_md_block_is_cache_safe() -> None:
    from agent.core.agent.prompt_sections.core_sections import CORE_AGENTS_MD_BLOCK

    assert CORE_AGENTS_MD_BLOCK.cache_safe is True


# ---------------------------------------------------------------------------
# skeleton 段位
# ---------------------------------------------------------------------------


def test_skeleton_places_agents_md_after_custom_before_memory() -> None:
    from agent.core.agent.prompt_sections.core_sections import (
        CORE_AGENTS_MD_BLOCK,
        CORE_MEMORY_BLOCK,
    )
    from agent.core.agent.prompt_sections.skeleton import (
        KERNEL_PROMPT_SKELETON,
        _SLOT_CUSTOM,
    )

    names = [s.name for s in KERNEL_PROMPT_SKELETON]
    assert CORE_AGENTS_MD_BLOCK.name in names
    idx_agents = names.index(CORE_AGENTS_MD_BLOCK.name)
    idx_custom = names.index(_SLOT_CUSTOM.name)
    idx_memory = names.index(CORE_MEMORY_BLOCK.name)
    assert idx_custom < idx_agents < idx_memory


def test_skeleton_satisfies_cache_safe_invariant_with_agents_md() -> None:
    # 段位正确则整套 skeleton 仍满足 cache_safe 不变量（不抛 ValueError）。
    from agent.core.agent.prompt_sections.skeleton import build_kernel_prompt_skeleton

    sections = build_kernel_prompt_skeleton()
    ctx = PromptContext(
        agents_md_content="x",
        render_mode=RenderMode.RUNTIME,
    )
    # assemble_system_prompt 校验不变量；不抛即通过。
    assemble_system_prompt(sections, ctx)


# ---------------------------------------------------------------------------
# wiring 透传
# ---------------------------------------------------------------------------


def test_wiring_threads_agents_md_content() -> None:
    from agent.core.agent.prompt_sections.wiring import (
        build_prompt_context_from_metadata,
    )

    ctx = build_prompt_context_from_metadata(
        metadata={},
        available_tools=[],
        available_skills=[],
        current_datetime="2026-01-01T00:00:00Z",
        cwd="/tmp/ws",
        flags={},
        agents_md_content="workspace conventions",
    )
    assert ctx.agents_md_content == "workspace conventions"
