"""Tests for ProductProfile.prompt_sections field and bootstrap assembly (feat-379-M1 R6)."""

from __future__ import annotations

import pytest


def test_product_profile_has_prompt_sections_field():
    """ProductProfile must accept a prompt_sections kwarg."""
    from agent.products.base import ProductProfile
    from agent.core.agent.prompt_sections.base import PromptSection

    sec = PromptSection(name="test.section", render=lambda ctx: "hello")
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        prompt_sections=(sec,),
    )
    assert len(profile.prompt_sections) == 1
    assert profile.prompt_sections[0].name == "test.section"


def test_product_profile_prompt_sections_defaults_to_empty():
    """prompt_sections must default to empty tuple when not supplied."""
    from agent.products.base import ProductProfile

    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    assert profile.prompt_sections == ()


def test_pa_profile_has_prompt_sections():
    """PA profile must include PA_SECTIONS in prompt_sections."""
    from agent.products.personal_assistant.profile import PERSONAL_ASSISTANT_PROFILE

    assert len(PERSONAL_ASSISTANT_PROFILE.prompt_sections) > 0
    names = [s.name for s in PERSONAL_ASSISTANT_PROFILE.prompt_sections]
    assert "pa.identity" in names
    assert "pa.communication_context" in names


def test_lc_profile_has_prompt_sections():
    """LC profile must include LC_SECTIONS in prompt_sections."""
    from agent.products.local_coding.profile import LOCAL_CODING_PROFILE

    assert len(LOCAL_CODING_PROFILE.prompt_sections) > 0
    names = [s.name for s in LOCAL_CODING_PROFILE.prompt_sections]
    assert "lc.identity" in names


def test_resolved_product_config_has_prompt_sections():
    """ResolvedProductConfig must expose prompt_sections list after bootstrap."""
    from agent.products.base import ResolvedProductConfig
    from agent.core.agent.prompt_sections.base import PromptSection

    sec = PromptSection(name="test.s", render=lambda ctx: "x")
    config = ResolvedProductConfig(
        product_id="test",
        resolved_system_prompt="",
        tool_registry=None,
        hook_registry=None,
        session_store=None,
        prompt_sections=[sec],
    )
    assert len(config.prompt_sections) == 1
