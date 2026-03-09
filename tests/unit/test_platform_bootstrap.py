"""Unit tests: bootstrap_product returns a ResolvedProductConfig."""

from pathlib import Path

from nano_multiagent.platform.bootstrap import bootstrap_product
from nano_multiagent.platform.product import ProductProfile, ResolvedProductConfig


def test_bootstrap_product_returns_resolved_config(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        default_system_prompt="You are a test assistant.",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert isinstance(resolved, ResolvedProductConfig)


def test_bootstrap_product_resolved_system_prompt_matches_profile(tmp_path: Path) -> None:
    expected_prompt = "You are a test assistant."
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        default_system_prompt=expected_prompt,
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.resolved_system_prompt == expected_prompt


def test_bootstrap_product_resolved_config_has_product_id(tmp_path: Path) -> None:
    profile = ProductProfile(
        product_id="my_product",
        display_name="My Product",
        config_namespace="myproduct",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.product_id == "my_product"


def test_bootstrap_product_tool_registry_not_none(tmp_path: Path) -> None:
    """bootstrap must wire a ToolRegistry (not None) for the product."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.tool_registry is not None


def test_bootstrap_product_hook_registry_not_none(tmp_path: Path) -> None:
    """bootstrap must wire a HookRegistry (not None) for the product."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    assert resolved.hook_registry is not None
