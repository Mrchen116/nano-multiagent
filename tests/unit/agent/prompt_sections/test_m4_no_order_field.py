"""M4 R2: PromptSection 无 order 字段 — Red 测试.

决策 16: 删 PromptSection.order, 顺序由编排列表位置决定。
cache_safe 不变量校验改为列表位置校验（volatile 段索引 > 所有 stable 段索引）。

这个测试在 M4 实施 R2 之前是红的（PromptSection 仍有 order 字段）。
实施后变绿。
"""
from __future__ import annotations

import dataclasses
import pytest

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    PromptSection,
    assemble_system_prompt,
)


# ---------------------------------------------------------------------------
# R2-A: PromptSection 无 order 字段
# ---------------------------------------------------------------------------

def test_prompt_section_has_no_order_field():
    """决策 16: PromptSection 不应有 order 字段。"""
    fields = {f.name for f in dataclasses.fields(PromptSection)}
    assert "order" not in fields, (
        "PromptSection must not have 'order' field after M4 R2 — "
        "ordering is by list position, not order magic numbers"
    )


def test_prompt_section_can_be_constructed_without_order():
    """构造 PromptSection 不需要 order 参数。"""
    sec = PromptSection(name="test.section", render=lambda ctx: "hello")
    assert sec.name == "test.section"


# ---------------------------------------------------------------------------
# R2-B: assemble_system_prompt 按列表位置顺序
# ---------------------------------------------------------------------------

def _ctx() -> PromptContext:
    return PromptContext()


def _sec(name: str, text: str, *, cache_safe: bool = True) -> PromptSection:
    """Helper: 不传 order，顺序由列表位置决定。"""
    return PromptSection(name=name, render=lambda ctx, t=text: t, cache_safe=cache_safe)


def test_assemble_uses_list_position_order():
    """assemble 按传入列表的位置顺序输出，不按 order 数字。"""
    sections = [
        _sec("first", "First"),
        _sec("second", "Second"),
        _sec("third", "Third"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "First\n\nSecond\n\nThird"


def test_assemble_list_position_reversed_order():
    """传入列表倒序，输出也倒序（无 order 重排）。"""
    sections = [
        _sec("z", "Z"),
        _sec("a", "A"),
    ]
    result = assemble_system_prompt(sections, _ctx())
    assert result == "Z\n\nA"


# ---------------------------------------------------------------------------
# R2-C: cache_safe 不变量改为列表位置校验
# ---------------------------------------------------------------------------

def test_cache_safe_invariant_passes_when_volatile_at_end():
    """volatile 段（cache_safe=False）在列表末尾 → 不变量满足。"""
    sections = [
        _sec("stable_1", "S1", cache_safe=True),
        _sec("stable_2", "S2", cache_safe=True),
        _sec("volatile", "V", cache_safe=False),
    ]
    # Must not raise
    assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_fails_when_volatile_before_stable():
    """volatile 段在 stable 段之前（列表位置）→ 校验报错。"""
    sections = [
        _sec("volatile", "V", cache_safe=False),
        _sec("stable", "S", cache_safe=True),
    ]
    with pytest.raises(ValueError, match="cache_safe"):
        assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_passes_when_all_stable():
    """全 stable → 不变量自然满足。"""
    sections = [
        _sec("a", "A", cache_safe=True),
        _sec("b", "B", cache_safe=True),
    ]
    assemble_system_prompt(sections, _ctx())


def test_cache_safe_invariant_fails_volatile_in_middle():
    """volatile 段在两个 stable 段之间 → 列表位置校验报错。"""
    sections = [
        _sec("stable_a", "SA", cache_safe=True),
        _sec("volatile", "V", cache_safe=False),
        _sec("stable_b", "SB", cache_safe=True),
    ]
    with pytest.raises(ValueError, match="cache_safe"):
        assemble_system_prompt(sections, _ctx())
