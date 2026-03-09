"""Integration tests: bootstrap_product wires a usable ToolRegistry."""

from pathlib import Path

from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT
from nano_multiagent.platform.bootstrap import bootstrap_product
from nano_multiagent.platform.product import ProductProfile
from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE


def test_bootstrap_builtin_tools_are_registered(tmp_path: Path) -> None:
    """Bootstrap wires built-in tools so standard tool names are available."""
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
    )
    resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
    registry = resolved.tool_registry
    assert registry is not None
    tool_names = {spec.name for spec in registry.list_specs()}
    # At minimum the core coding built-ins must be present
    assert "read" in tool_names
    assert "bash" in tool_names


def test_bootstrap_local_coding_tool_ids(tmp_path: Path) -> None:
    """bootstrap_product(local_coding) provides exactly the declared 5 tool ids."""
    resolved = bootstrap_product(profile=LOCAL_CODING_PROFILE, repo_root=tmp_path)
    assert resolved.tool_registry is not None
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert tool_names == {"read", "write", "edit", "bash", "task"}


def test_bootstrap_local_coding_system_prompt_injected(tmp_path: Path) -> None:
    """bootstrap_product(local_coding) resolved_system_prompt equals CODING_SYSTEM_PROMPT."""
    resolved = bootstrap_product(profile=LOCAL_CODING_PROFILE, repo_root=tmp_path)
    assert resolved.resolved_system_prompt == CODING_SYSTEM_PROMPT
