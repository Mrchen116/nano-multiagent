"""Contract tests: ProductProfile and ResolvedProductConfig field stability."""

from dataclasses import fields, is_dataclass

from nano_multiagent.platform.product import ProductProfile, ResolvedProductConfig


def test_product_profile_is_dataclass() -> None:
    assert is_dataclass(ProductProfile)


def test_product_profile_required_fields_stable() -> None:
    field_names = {f.name for f in fields(ProductProfile)}
    required = {
        "product_id",
        "display_name",
        "config_namespace",
        "default_system_prompt",
        "default_tool_ids",
        "default_hook_modules",
        "skill_search_policy",
        "session_store_policy",
        "safety_defaults",
        "capabilities",
    }
    assert required <= field_names, f"missing fields: {required - field_names}"


def test_resolved_product_config_is_dataclass() -> None:
    assert is_dataclass(ResolvedProductConfig)


def test_resolved_product_config_required_fields_stable() -> None:
    field_names = {f.name for f in fields(ResolvedProductConfig)}
    required = {
        "product_id",
        "resolved_system_prompt",
        "tool_registry",
        "hook_registry",
        "session_store",
    }
    assert required <= field_names, f"missing fields: {required - field_names}"
