"""Unit tests: PERSONAL_ASSISTANT_PROFILE complete field declarations (M77)."""

from pathlib import Path

from agent.products.base import ProductProfile
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

_PRODUCT_ROOT = Path(__file__).resolve().parents[2] / "src" / "agent" / "products" / "personal_assistant"


def test_personal_assistant_profile_is_product_profile() -> None:
    assert isinstance(PERSONAL_ASSISTANT_PROFILE, ProductProfile)


def test_personal_assistant_profile_product_id() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.product_id == "personal_assistant"


def test_personal_assistant_profile_config_namespace() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.config_namespace == "nanoassistant"


def test_personal_assistant_profile_global_config_home() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.global_config_home == Path("~/.nanoassistant")


def test_personal_assistant_profile_workspace_config_dirname() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.workspace_config_dirname == ".nanoassistant"


def test_personal_assistant_profile_session_db_filename() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.session_db_filename == "sessions.sqlite3"


def test_personal_assistant_profile_compat_skill_roots_include_current_skill_homes() -> None:
    roots = {str(path) for path in PERSONAL_ASSISTANT_PROFILE.compat_skill_roots}
    assert "~/.claude/skills" in roots
    assert "~/.codex/skills" in roots


def test_personal_assistant_profile_default_system_prompt_non_empty() -> None:
    """personal_assistant profile must have a non-empty system prompt."""
    assert PERSONAL_ASSISTANT_PROFILE.default_system_prompt is not None
    assert len(PERSONAL_ASSISTANT_PROFILE.default_system_prompt.strip()) > 0


def test_personal_assistant_profile_system_prompt_not_coding() -> None:
    """personal_assistant system prompt must not reference coding/code assistant semantics."""
    prompt = (PERSONAL_ASSISTANT_PROFILE.default_system_prompt or "").lower()
    # Must not describe itself as a coding assistant.
    assert "coding assistant" not in prompt
    assert "code assistant" not in prompt


def test_personal_assistant_profile_default_tool_ids_keep_conservative_defaults() -> None:
    """personal_assistant must default to read/task and keep send_message opt-in."""
    assert PERSONAL_ASSISTANT_PROFILE.default_tool_ids is not None
    tool_ids = set(PERSONAL_ASSISTANT_PROFILE.default_tool_ids)
    assert tool_ids == {"read", "task"}
    assert "send_message" not in tool_ids
    assert "write" not in tool_ids
    assert "edit" not in tool_ids
    assert "bash" not in tool_ids


def test_personal_assistant_profile_optional_tool_ids_include_send_message() -> None:
    """personal_assistant must advertise send_message as a supported optional tool."""
    assert PERSONAL_ASSISTANT_PROFILE.optional_tool_ids == ["send_message"]


def test_personal_assistant_profile_default_hook_modules_no_bash_risk_gate() -> None:
    """personal_assistant hook modules must not include bash_risk_gate (no bash tool)."""
    assert PERSONAL_ASSISTANT_PROFILE.default_hook_modules is not None
    modules = set(PERSONAL_ASSISTANT_PROFILE.default_hook_modules)
    assert "bash_risk_gate" not in modules
    assert "default_status" in modules
    assert "usage_metrics" in modules


def test_personal_assistant_profile_capabilities() -> None:
    """personal_assistant must declare IM/heartbeat/memory capabilities."""
    caps = PERSONAL_ASSISTANT_PROFILE.capabilities
    assert caps.get("im") is True
    assert caps.get("heartbeat") is True
    assert caps.get("memory") is True


def test_personal_assistant_profile_layout_contracts_present() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.memory_layout == {"kind": "personal_memory"}
    assert PERSONAL_ASSISTANT_PROFILE.heartbeat_layout == {"transport": "assistant_presence"}


def test_personal_assistant_product_directory_contains_extension_roots() -> None:
    assert (_PRODUCT_ROOT / "tools").is_dir()
    assert (_PRODUCT_ROOT / "hooks").is_dir()
    assert (_PRODUCT_ROOT / "skills").is_dir()
