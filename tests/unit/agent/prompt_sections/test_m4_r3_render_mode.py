"""M4 R3: render_mode + banner 迁移 — Red 测试.

决策 17: banner 从 MemoryStore._render_block 移到 core 段 render。
决策 18: PromptContext 新增 render_mode: RenderMode (RUNTIME/PREVIEW)；
         memory_block → memory_content (纯内容), user_profile_block → user_profile_content。
决策 19: preview 占位符逻辑下沉 core，core 段 render 按 render_mode 分支。
决策 21: 段 render 三态 (PREVIEW/RUNTIME+数据/RUNTIME+无数据)。

M4 退出标准:
- [worker] banner 字符串（══/MEMORY (your personal notes)）只在 core 段 render、不在 MemoryStore
- [reviewer] preview 中 volatile 段就地显示完整 banner + 动态槽占位符

这些测试在 R3 实施之前是红的。
"""
from __future__ import annotations

import enum
import pytest

from agent.core.agent.prompt_sections.base import PromptContext
from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS
from agent.core.memory.store import MemoryStore, MemoryEntry, MemorySource
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# R3-A: PromptContext 有 render_mode 字段
# ---------------------------------------------------------------------------

def test_prompt_context_has_render_mode_field():
    """决策 18: PromptContext 必须有 render_mode 字段。"""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PromptContext)}
    assert "render_mode" in fields, (
        "PromptContext must have render_mode field after M4 R3"
    )


def test_render_mode_is_enum_with_runtime_and_preview():
    """render_mode 必须支持 RUNTIME 和 PREVIEW 两个值。"""
    from agent.core.agent.prompt_sections.base import RenderMode
    assert hasattr(RenderMode, "RUNTIME")
    assert hasattr(RenderMode, "PREVIEW")


# ---------------------------------------------------------------------------
# R3-B: PromptContext 使用 memory_content 而非 memory_block
# ---------------------------------------------------------------------------

def test_prompt_context_has_memory_content_field():
    """决策 18: PromptContext 改为 memory_content (纯内容，无 banner)。"""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PromptContext)}
    assert "memory_content" in fields, (
        "PromptContext must have memory_content field (pure content, no banner)"
    )


def test_prompt_context_has_user_profile_content_field():
    """决策 18: user_profile_block → user_profile_content。"""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PromptContext)}
    assert "user_profile_content" in fields, (
        "PromptContext must have user_profile_content field"
    )


# ---------------------------------------------------------------------------
# R3-C: MemoryStore.format_for_prompt 不再包含 banner
# ---------------------------------------------------------------------------

def _build_store_with_entries(entries: list[str], target: str = "memory") -> MemoryStore:
    tmp = Path(tempfile.mkdtemp())
    store = MemoryStore(memory_root=tmp)
    src = MemorySource(session_id="test", timestamp=0.0)
    for text in entries:
        store.add(target, MemoryEntry(text=text, source=src))
    return store


def test_memory_store_format_for_prompt_returns_pure_content():
    """决策 17: MemoryStore.format_for_prompt 只返回纯内容（无 banner）。"""
    store = _build_store_with_entries(["some fact"])
    content = store.format_for_prompt("memory")
    assert content is not None
    # Banner text must NOT be in the returned value (banner moved to core segment)
    assert "══" not in content, (
        "MemoryStore.format_for_prompt must return pure content without banner separators"
    )
    assert "MEMORY (your personal notes)" not in content, (
        "MemoryStore.format_for_prompt must return pure content without banner title"
    )


def test_memory_store_format_for_prompt_still_has_content():
    """MemoryStore.format_for_prompt 仍然返回 entry 内容。"""
    store = _build_store_with_entries(["User prefers dark mode"])
    content = store.format_for_prompt("memory")
    assert content is not None
    assert "User prefers dark mode" in content


# ---------------------------------------------------------------------------
# R3-D: core.memory_block render 三态 — 需要 render_mode
# ---------------------------------------------------------------------------

def _get_memory_block_section():
    for s in CORE_SECTIONS:
        if s.name == "core.memory_block":
            return s
    raise KeyError("core.memory_block not in CORE_SECTIONS")


def _ctx_runtime_with_content(content: str) -> PromptContext:
    from agent.core.agent.prompt_sections.base import RenderMode
    return PromptContext(
        memory_content=content,
        render_mode=RenderMode.RUNTIME,
    )


def _ctx_preview() -> PromptContext:
    from agent.core.agent.prompt_sections.base import RenderMode
    return PromptContext(
        memory_content=None,
        render_mode=RenderMode.PREVIEW,
    )


def _ctx_runtime_no_content() -> PromptContext:
    from agent.core.agent.prompt_sections.base import RenderMode
    return PromptContext(
        memory_content=None,
        render_mode=RenderMode.RUNTIME,
    )


def test_memory_block_render_runtime_with_content_has_banner():
    """RUNTIME + 数据 → banner + 真实内容（决策 21 第二态）。"""
    seg = _get_memory_block_section()
    ctx = _ctx_runtime_with_content("some fact")
    result = seg.render(ctx)
    assert result is not None
    assert "══" in result, "RUNTIME render must include banner separators"
    assert "MEMORY (your personal notes)" in result, "RUNTIME render must include banner title"
    assert "some fact" in result, "RUNTIME render must include actual content"


def test_memory_block_render_runtime_no_content_is_none():
    """RUNTIME + 无数据 → None（段失活，决策 21 第三态）。"""
    seg = _get_memory_block_section()
    ctx = _ctx_runtime_no_content()
    result = seg.render(ctx)
    assert result is None, "RUNTIME+no data: segment must return None (deactivate)"


def test_memory_block_render_preview_has_banner_and_placeholder():
    """PREVIEW → banner + <运行时注入:...> 占位符（决策 21 第一态）。"""
    seg = _get_memory_block_section()
    ctx = _ctx_preview()
    result = seg.render(ctx)
    assert result is not None, "PREVIEW: segment must render (not None)"
    assert "══" in result, "PREVIEW render must include banner separators"
    assert "MEMORY (your personal notes)" in result, "PREVIEW render must include banner title"
    assert "运行时注入" in result, "PREVIEW render must include '运行时注入' placeholder text"


def test_memory_block_render_preview_banner_bytes_same_as_runtime():
    """PREVIEW 与 RUNTIME 的 banner 字节一致（只有动态槽不同）。"""
    seg = _get_memory_block_section()

    preview_result = seg.render(_ctx_preview())
    runtime_result = seg.render(_ctx_runtime_with_content("any content"))

    assert preview_result is not None and runtime_result is not None

    # Both should have the same separator
    sep = "═" * 46
    assert sep in preview_result
    assert sep in runtime_result

    # Banner title must be identical in both
    assert "MEMORY (your personal notes)" in preview_result
    assert "MEMORY (your personal notes)" in runtime_result
