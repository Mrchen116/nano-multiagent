"""Unit tests: ResolvedProductConfig.default_tool_ids field and bootstrap optional merging (M250)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.products.base import ResolvedProductConfig


def test_resolved_product_config_has_default_tool_ids_field() -> None:
    """ResolvedProductConfig must expose default_tool_ids field."""
    config = ResolvedProductConfig(
        product_id="test",
        resolved_system_prompt="",
        tool_registry=None,
        hook_registry=None,
        session_store=None,
    )
    assert hasattr(config, "default_tool_ids")
    assert config.default_tool_ids is None


def test_resolved_product_config_default_tool_ids_can_be_set() -> None:
    """ResolvedProductConfig.default_tool_ids accepts a list of tool ids."""
    config = ResolvedProductConfig(
        product_id="test",
        resolved_system_prompt="",
        tool_registry=None,
        hook_registry=None,
        session_store=None,
        default_tool_ids=["read", "write"],
    )
    assert config.default_tool_ids == ["read", "write"]


def test_bootstrap_personal_assistant_registry_includes_optional_send_message(
    tmp_path: Path,
) -> None:
    """bootstrap_product must include send_message in the full registry (optional pool) so allowlist can find it."""
    from agent.platform.bootstrap import bootstrap_product
    from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.tool_registry is not None
    # send_message must be discoverable in the full registry
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert "send_message" in tool_names, (
        "send_message must be in full tool registry so tool_allowlist can find it; "
        f"got: {sorted(tool_names)}"
    )


def test_bootstrap_personal_assistant_default_tool_ids_excludes_send_message(
    tmp_path: Path,
) -> None:
    """Resolved config must carry default_tool_ids that excludes send_message."""
    from agent.platform.bootstrap import bootstrap_product
    from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.default_tool_ids is not None
    assert "send_message" not in resolved.default_tool_ids
    assert "read" in resolved.default_tool_ids


def test_bootstrap_personal_assistant_resolved_config_default_tool_ids_matches_profile(
    tmp_path: Path,
) -> None:
    """ResolvedProductConfig.default_tool_ids must equal profile.default_tool_ids."""
    from agent.platform.bootstrap import bootstrap_product
    from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.default_tool_ids == PERSONAL_ASSISTANT_PROFILE.default_tool_ids
