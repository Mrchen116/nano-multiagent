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


def test_personal_assistant_profile_default_system_prompt_empty_for_segment_assembly() -> None:
    """feat-385 decision 11: default_system_prompt is "" — segment assembly replaces f-string."""
    assert PERSONAL_ASSISTANT_PROFILE.default_system_prompt == ""
    # Verify PA has prompt_sections for segment-based assembly
    assert PERSONAL_ASSISTANT_PROFILE.prompt_sections


def test_personal_assistant_profile_system_prompt_not_coding() -> None:
    """personal_assistant segments must not reference coding/code assistant semantics."""
    # feat-385: check against assembled segment content, not the deleted prompts.py
    from agent.products.personal_assistant.prompt_sections import PA_SECTIONS
    from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
    ctx = PromptContext(current_datetime="2026-01-01T00:00:00", cwd="/ws")
    prompt = assemble_system_prompt(list(PA_SECTIONS), ctx).lower()
    assert "coding assistant" not in prompt
    assert "code assistant" not in prompt


def test_personal_assistant_profile_default_tool_ids() -> None:
    """personal_assistant includes full set of default tools including self-evolution tools."""
    assert PERSONAL_ASSISTANT_PROFILE.default_tool_ids is not None
    tool_ids = set(PERSONAL_ASSISTANT_PROFILE.default_tool_ids)
    assert {"read", "write", "edit", "bash", "agent", "web_fetch", "web_search"} <= tool_ids
    assert "send_message" not in tool_ids
    # Self-evolution tools (feat-349-M3 wiring).
    assert "skill_manage" in tool_ids
    assert "memory" in tool_ids


def test_personal_assistant_profile_optional_tool_ids_include_send_message() -> None:
    """personal_assistant must advertise send_message as a supported optional tool."""
    assert PERSONAL_ASSISTANT_PROFILE.optional_tool_ids == ["send_message"]


def test_personal_assistant_profile_default_hook_modules_no_bash_risk_gate() -> None:
    """personal_assistant hook modules must not include bash_risk_gate and must include self_improvement."""
    assert PERSONAL_ASSISTANT_PROFILE.default_hook_modules is not None
    modules = set(PERSONAL_ASSISTANT_PROFILE.default_hook_modules)
    assert "bash_risk_gate" not in modules
    assert "default_status" in modules
    assert "usage_metrics" in modules
    # Self-improvement background hook (feat-349-M3 wiring).
    assert "self_improvement" in modules


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
