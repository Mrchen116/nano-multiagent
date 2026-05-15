"""Unit tests: LOCAL_CODING_PROFILE matches current coding defaults."""

from pathlib import Path

from agent.core.agent.prompting import CODING_SYSTEM_PROMPT
from agent.products.base import ProductProfile
from agent.products.local_coding import LOCAL_CODING_PROFILE

_PRODUCT_ROOT = Path(__file__).resolve().parents[2] / "src" / "agent" / "products" / "local_coding"


def test_local_coding_profile_is_product_profile() -> None:
    assert isinstance(LOCAL_CODING_PROFILE, ProductProfile)


def test_local_coding_profile_product_id() -> None:
    assert LOCAL_CODING_PROFILE.product_id == "local_coding"


def test_local_coding_profile_config_namespace() -> None:
    # Must match the global config directory documented in the architecture.
    assert LOCAL_CODING_PROFILE.config_namespace == "nanocode"


def test_local_coding_profile_system_prompt_uses_coding_system_prompt() -> None:
    """local_coding profile must use CODING_SYSTEM_PROMPT, not the generic DEFAULT_SYSTEM_PROMPT."""
    assert LOCAL_CODING_PROFILE.default_system_prompt == CODING_SYSTEM_PROMPT
    assert "coding assistant" in LOCAL_CODING_PROFILE.default_system_prompt or \
           "expert coding" in LOCAL_CODING_PROFILE.default_system_prompt


def test_local_coding_profile_has_display_name() -> None:
    assert LOCAL_CODING_PROFILE.display_name
    assert isinstance(LOCAL_CODING_PROFILE.display_name, str)


def test_local_coding_profile_default_tool_ids() -> None:
    """local_coding profile must include self-evolution tools alongside core tools."""
    assert LOCAL_CODING_PROFILE.default_tool_ids is not None
    tool_ids = set(LOCAL_CODING_PROFILE.default_tool_ids)
    # Core coding tools.
    assert {"read", "write", "edit", "bash", "agent", "task_stop"} <= tool_ids
    # Self-evolution tools (feat-349-M3 wiring).
    assert "skill_manage" in tool_ids
    assert "memory" in tool_ids


def test_local_coding_profile_default_hook_modules() -> None:
    """local_coding profile must include self_improvement hook."""
    assert LOCAL_CODING_PROFILE.default_hook_modules is not None
    assert len(LOCAL_CODING_PROFILE.default_hook_modules) > 0
    # All 4 original builtin hook modules must be declared.
    modules = set(LOCAL_CODING_PROFILE.default_hook_modules)
    assert "auto_mode_gate" in modules  # M1: replaced bash_risk_gate with auto_mode_gate
    assert "default_status" in modules
    assert "realtime_stream" in modules
    assert "usage_metrics" in modules
    # Self-improvement background hook (feat-349-M3 wiring).
    assert "self_improvement" in modules


def test_local_coding_profile_layout_contracts_present() -> None:
    assert LOCAL_CODING_PROFILE.optional_tool_ids == []
    assert LOCAL_CODING_PROFILE.memory_layout == {"kind": "workspace_scoped"}
    assert LOCAL_CODING_PROFILE.heartbeat_layout == {"transport": "runtime_events"}


def test_local_coding_product_directory_contains_extension_roots() -> None:
    assert (_PRODUCT_ROOT / "tools").is_dir()
    assert (_PRODUCT_ROOT / "hooks").is_dir()
    assert (_PRODUCT_ROOT / "skills").is_dir()
