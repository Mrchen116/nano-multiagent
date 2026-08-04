"""Behavioral tests for prompt-section assembly and prompt resolution."""

from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import (
    PromptContext,
    PromptSection,
    assemble_system_prompt,
    resolve_effective_prompt,
)


def _section(
    name: str,
    text: str | None,
    *,
    cache_safe: bool = True,
    enabled: bool = True,
) -> PromptSection:
    return PromptSection(
        name=name,
        render=lambda _ctx: text,
        enabled_when=lambda _ctx: enabled,
        cache_safe=cache_safe,
    )


def test_assemble_preserves_list_order_and_omits_inactive_content() -> None:
    sections = [
        _section("third", "third"),
        _section("disabled", "disabled", enabled=False),
        _section("empty", ""),
        _section("first", "first"),
        _section("none", None),
    ]

    assert assemble_system_prompt(sections, PromptContext()) == "third\n\nfirst"


def test_assemble_passes_the_same_context_to_gate_and_renderer() -> None:
    seen: list[tuple[str, PromptContext]] = []
    ctx = PromptContext(flags={"enabled": True})
    section = PromptSection(
        name="conditional",
        enabled_when=lambda actual: (
            seen.append(("gate", actual)) or actual.flags["enabled"]
        ),
        render=lambda actual: seen.append(("render", actual)) or "rendered",
    )

    assert assemble_system_prompt([section], ctx) == "rendered"
    assert seen == [("gate", ctx), ("render", ctx)]


@pytest.mark.parametrize(
    "sections, should_raise",
    [
        ([_section("stable", "s"), _section("volatile", "v", cache_safe=False)], False),
        ([_section("volatile", "v", cache_safe=False), _section("stable", "s")], True),
        (
            [
                _section("stable", "s"),
                _section("volatile", "v", cache_safe=False),
                _section("stable-again", "s2"),
            ],
            True,
        ),
    ],
)
def test_assemble_enforces_a_contiguous_cache_safe_prefix(
    sections: list[PromptSection], should_raise: bool
) -> None:
    if should_raise:
        with pytest.raises(ValueError, match="cache_safe"):
            assemble_system_prompt(sections, PromptContext())
    else:
        assert assemble_system_prompt(sections, PromptContext()) == "s\n\nv"


@pytest.mark.parametrize("override", [None, "", "   "])
def test_resolve_assembles_sections_without_a_nonempty_override(
    override: str | None,
) -> None:
    assert (
        resolve_effective_prompt(
            sections=[_section("assembled", "assembled")],
            ctx=PromptContext(),
            override=override,
        )
        == "assembled"
    )


def test_resolve_uses_a_nonempty_override_without_rendering_sections() -> None:
    rendered = False

    def render(_ctx: PromptContext) -> str:
        nonlocal rendered
        rendered = True
        return "assembled"

    result = resolve_effective_prompt(
        sections=[PromptSection(name="assembled", render=render)],
        ctx=PromptContext(),
        override="override",
    )

    assert result == "override"
    assert rendered is False
