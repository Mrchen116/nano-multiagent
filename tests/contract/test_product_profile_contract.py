"""Contract tests: canonical ProductProfile and ResolvedProductConfig field stability."""

from dataclasses import fields, is_dataclass
from pathlib import Path

from agent.platform.product import (
    ProductProfile as LegacyProductProfile,
    ResolvedProductConfig as LegacyResolvedProductConfig,
)
from agent.products.base import ProductProfile, ResolvedProductConfig

_PRODUCTS_ROOT = Path(__file__).resolve().parents[2] / "src" / "agent" / "products"


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
        "optional_tool_ids",
        "default_hook_modules",
        "skill_search_policy",
        "session_store_policy",
        "memory_layout",
        "heartbeat_layout",
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


def test_platform_product_shim_exports_canonical_contracts() -> None:
    assert LegacyProductProfile is ProductProfile
    assert LegacyResolvedProductConfig is ResolvedProductConfig


def test_product_directories_expose_extension_roots() -> None:
    for product_name in ("local_coding", "personal_assistant"):
        product_root = _PRODUCTS_ROOT / product_name
        assert (product_root / "tools").is_dir()
        assert (product_root / "hooks").is_dir()
        assert (product_root / "skills").is_dir()
