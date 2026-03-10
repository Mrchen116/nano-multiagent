"""Unit tests: canonical ProductProfile and ResolvedProductConfig instantiation."""

from nano_multiagent.products.base import ProductProfile, ResolvedProductConfig


def test_product_profile_instantiation_with_defaults() -> None:
    profile = ProductProfile(
        product_id="test_product",
        display_name="Test Product",
        config_namespace="test",
    )
    assert profile.product_id == "test_product"
    assert profile.display_name == "Test Product"
    assert profile.config_namespace == "test"
    # Fields with defaults should be set.
    assert profile.default_system_prompt is None or isinstance(profile.default_system_prompt, str)
    assert isinstance(profile.default_tool_ids, (list, tuple, type(None)))
    assert isinstance(profile.default_hook_modules, (list, tuple, type(None)))
    assert profile.optional_tool_ids == []
    assert profile.memory_layout == {}
    assert profile.heartbeat_layout == {}


def test_product_profile_accepts_all_fields() -> None:
    profile = ProductProfile(
        product_id="coding",
        display_name="Coding CLI",
        config_namespace="nanocode",
        default_system_prompt="You are a coding assistant.",
        default_tool_ids=["read", "bash", "edit", "write", "glob"],
        optional_tool_ids=["task"],
        default_hook_modules=[],
        skill_search_policy="workspace",
        session_store_policy="sqlite",
        memory_layout={"kind": "ephemeral"},
        heartbeat_layout={"transport": "manual"},
        safety_defaults={"allow_network": False},
        capabilities={"multi_tool": True},
    )
    assert profile.product_id == "coding"
    assert profile.default_tool_ids == ["read", "bash", "edit", "write", "glob"]
    assert profile.optional_tool_ids == ["task"]
    assert profile.memory_layout == {"kind": "ephemeral"}
    assert profile.heartbeat_layout == {"transport": "manual"}
    assert profile.safety_defaults == {"allow_network": False}
    assert profile.capabilities == {"multi_tool": True}


def test_resolved_product_config_accepts_none_fields() -> None:
    """ResolvedProductConfig fields are allowed to be None before bootstrap wires them."""
    resolved = ResolvedProductConfig(
        product_id="coding",
        resolved_system_prompt="You are a coding assistant.",
        tool_registry=None,
        hook_registry=None,
        session_store=None,
        config_resolver=None,
    )
    assert resolved.product_id == "coding"
    assert resolved.tool_registry is None
    assert resolved.config_resolver is None
