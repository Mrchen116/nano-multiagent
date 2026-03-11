"""Integration tests: bootstrap_product wires a usable ToolRegistry."""

from pathlib import Path

from agent.core.agent.prompting import CODING_SYSTEM_PROMPT
from agent.core.skills.discovery import default_skill_search_roots
from agent.platform.bootstrap import bootstrap_product
from agent.products.base import ProductProfile
from agent.products.local_coding import LOCAL_CODING_PROFILE
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTS_ROOT = _PROJECT_ROOT / "src" / "agent" / "products"


def _module_stems_with_source(resolved, *, source: str) -> set[str]:
    assert resolved.hook_registry is not None
    return {
        Path(h.file_path).stem
        for h in resolved.hook_registry.all_handlers()
        if h.file_path is not None and h.source == source
    }


def _tool_names(resolved) -> list[str]:
    assert resolved.tool_registry is not None
    return [spec.name for spec in resolved.tool_registry.list_specs()]


_PRODUCT_TOOL_DIRS = {
    "local_coding": _PRODUCTS_ROOT / "local_coding" / "tools",
    "personal_assistant": _PRODUCTS_ROOT / "personal_assistant" / "tools",
}

_PRODUCT_HOOK_DIRS = {
    "local_coding": _PRODUCTS_ROOT / "local_coding" / "hooks",
    "personal_assistant": _PRODUCTS_ROOT / "personal_assistant" / "hooks",
}

_PRODUCT_SKILL_DIRS = {
    "local_coding": _PRODUCTS_ROOT / "local_coding" / "skills",
    "personal_assistant": _PRODUCTS_ROOT / "personal_assistant" / "skills",
}

_PRODUCT_PROFILES = {
    "local_coding": LOCAL_CODING_PROFILE,
    "personal_assistant": PERSONAL_ASSISTANT_PROFILE,
}


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


def test_bootstrap_product_uses_product_hook_directory_as_default_layer(tmp_path: Path) -> None:
    for product_name, profile in _PRODUCT_PROFILES.items():
        resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
        product_stems = {path.stem for path in _PRODUCT_HOOK_DIRS[product_name].glob("*.py") if not path.name.startswith("_")}
        loaded_stems = _module_stems_with_source(resolved, source="product")
        assert product_stems <= loaded_stems


def test_bootstrap_product_exposes_product_default_tools_before_user_layers(tmp_path: Path) -> None:
    for product_name, profile in _PRODUCT_PROFILES.items():
        resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
        tool_names = _tool_names(resolved)
        product_tool_names = {path.stem for path in _PRODUCT_TOOL_DIRS[product_name].glob("*.py") if not path.name.startswith("_")}
        assert set(profile.default_tool_ids or []) <= set(tool_names)
        assert product_tool_names <= set(tool_names)


def test_bootstrap_product_resolver_skill_roots_include_product_default_layer(tmp_path: Path) -> None:
    for product_name, profile in _PRODUCT_PROFILES.items():
        resolved = bootstrap_product(profile=profile, repo_root=tmp_path)
        assert resolved.config_resolver is not None
        roots = default_skill_search_roots(
            workspace_root=tmp_path,
            config_resolver=resolved.config_resolver,
            product_skill_root=_PRODUCT_SKILL_DIRS[product_name],
        )
        assert roots[0] == _PRODUCT_SKILL_DIRS[product_name].resolve()
        assert roots[1] == tmp_path / profile.workspace_config_dirname / "skills"
