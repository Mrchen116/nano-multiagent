"""Unit tests for tools/loader ConfigResolver integration.

Verifies that build_tool_registry uses resolver-specified tool roots when a
ConfigResolver is provided, and falls back to .nano/tools otherwise.
"""

from pathlib import Path

from agent.platform.config.resolver import ConfigResolver
from agent.products.base import ProductProfile
from agent.platform.tools.loader import build_tool_registry


def _make_resolver(global_home: Path, workspace_root: Path | None = None) -> ConfigResolver:
    profile = ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=global_home,
        workspace_config_dirname=".testprod",
        session_db_filename="sessions.sqlite3",
        compat_skill_roots=[],
    )
    return ConfigResolver(profile=profile, workspace_root=workspace_root)


_TOOL_CODE = """
class ResolverTool:
    name = "resolver_test_tool"
    description = "Tool loaded via resolver"
    input_schema = {"type": "object", "properties": {}}

    def run(self, args, ctx):
        return "ok"

TOOL = ResolverTool()
"""

_LEGACY_TOOL_CODE = """
class LegacyNanoTool:
    name = "legacy_nano_tool"
    description = "Legacy tool"
    input_schema = {"type": "object", "properties": {}}

    def run(self, args, ctx):
        return "ok"

TOOL = LegacyNanoTool()
"""


def test_build_tool_registry_uses_resolver_workspace_tool_root(tmp_path: Path) -> None:
    """build_tool_registry loads tools from resolver workspace tool dir."""
    # Place tool in resolver-specified workspace tool dir (.testprod/tools)
    tool_dir = tmp_path / ".testprod" / "tools"
    tool_dir.mkdir(parents=True)
    (tool_dir / "resolver_tool.py").write_text(_TOOL_CODE)

    resolver = _make_resolver(
        global_home=tmp_path / ".global",
        workspace_root=tmp_path,
    )
    registry = build_tool_registry(
        repo_root=tmp_path,
        config_resolver=resolver,
    )
    tool_names = [spec.name for spec in registry.list_specs()]
    assert "resolver_test_tool" in tool_names


def test_build_tool_registry_uses_resolver_global_tool_root(tmp_path: Path) -> None:
    """build_tool_registry loads tools from resolver global tool dir."""
    global_tool_dir = tmp_path / ".global" / "tools"
    global_tool_dir.mkdir(parents=True)
    (global_tool_dir / "global_tool.py").write_text(_TOOL_CODE.replace(
        "resolver_test_tool", "global_resolver_tool"
    ).replace(
        "ResolverTool", "GlobalResolverTool"
    ))

    resolver = _make_resolver(global_home=tmp_path / ".global")
    registry = build_tool_registry(
        repo_root=tmp_path,
        config_resolver=resolver,
    )
    tool_names = [spec.name for spec in registry.list_specs()]
    assert "global_resolver_tool" in tool_names


def test_build_tool_registry_falls_back_to_nano_tools(tmp_path: Path) -> None:
    """Without config_resolver, tools loaded from legacy .nano/tools path."""
    tool_dir = tmp_path / ".nano" / "tools"
    tool_dir.mkdir(parents=True)
    (tool_dir / "legacy_tool.py").write_text(_LEGACY_TOOL_CODE)

    # No resolver: falls back to .nano/tools
    registry = build_tool_registry(repo_root=tmp_path)
    tool_names = [spec.name for spec in registry.list_specs()]
    assert "legacy_nano_tool" in tool_names


def test_build_tool_registry_with_resolver_does_not_load_nano_tools(tmp_path: Path) -> None:
    """When resolver is provided, legacy .nano/tools dir is NOT searched.

    This ensures the resolver fully controls tool discovery without the old
    hard-coded path sneaking in additional tools.
    """
    # Place a tool in the legacy location
    legacy_dir = tmp_path / ".nano" / "tools"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "legacy_tool.py").write_text(_LEGACY_TOOL_CODE)

    # No tool in resolver paths → registry should not have legacy tool
    resolver = _make_resolver(global_home=tmp_path / ".global", workspace_root=tmp_path)
    registry = build_tool_registry(repo_root=tmp_path, config_resolver=resolver)
    tool_names = [spec.name for spec in registry.list_specs()]
    assert "legacy_nano_tool" not in tool_names
