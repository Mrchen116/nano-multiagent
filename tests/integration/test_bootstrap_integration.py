"""Integration tests: bootstrap_product wires a usable ToolRegistry."""

from pathlib import Path

from nano_multiagent.platform.bootstrap import bootstrap_product
from nano_multiagent.platform.product import ProductProfile


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
