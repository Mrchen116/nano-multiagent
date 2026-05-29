"""Unit tests for canonical product profile packages and path fields.

Verifies that LOCAL_CODING_PROFILE and PERSONAL_ASSISTANT_PROFILE live under
`agent.products.*` and declare the expected package-level defaults.
"""

from pathlib import Path

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookAPI, HookRegistry
from agent.platform.bootstrap import bootstrap_product
from agent.platform.products.local_coding import (
    LOCAL_CODING_PROFILE as LEGACY_LOCAL_CODING_PROFILE,
)
from agent.platform.products.personal_assistant import (
    PERSONAL_ASSISTANT_PROFILE as LEGACY_PERSONAL_ASSISTANT_PROFILE,
)
from agent.products.local_coding import LOCAL_CODING_PROFILE
from agent.products.local_coding import defaults as local_coding_defaults
from agent.products.local_coding import hooks as local_coding_hooks
from agent.products.local_coding import toolsets as local_coding_toolsets
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE
from agent.products.personal_assistant import defaults as personal_assistant_defaults
from agent.products.personal_assistant import hooks as personal_assistant_hooks
from agent.products.personal_assistant import toolsets as personal_assistant_toolsets


def test_local_coding_profile_global_config_home() -> None:
    assert LOCAL_CODING_PROFILE.global_config_home == Path("~/.nanocode")


def test_local_coding_profile_workspace_config_dirname() -> None:
    assert LOCAL_CODING_PROFILE.workspace_config_dirname == ".nanocode"


def test_local_coding_profile_session_db_filename() -> None:
    assert LOCAL_CODING_PROFILE.session_db_filename == "sessions.sqlite3"


def test_local_coding_profile_compat_skill_roots_contains_codex() -> None:
    roots = LOCAL_CODING_PROFILE.compat_skill_roots
    assert any(str(r) == "~/.codex/skills" for r in roots), (
        f"Expected '~/.codex/skills' in compat_skill_roots, got: {roots}"
    )


def test_local_coding_package_exports_default_modules() -> None:
    assert local_coding_defaults.CONFIG_NAMESPACE == "nanocode"
    # prompts.py deleted; default_system_prompt="" signals segment assembly
    assert LOCAL_CODING_PROFILE.default_system_prompt == ""
    assert {"read", "write", "edit", "bash", "agent", "task_stop"} <= set(local_coding_toolsets.DEFAULT_TOOL_IDS)
    assert "skill_manage" in local_coding_toolsets.DEFAULT_TOOL_IDS
    assert "memory" in local_coding_toolsets.DEFAULT_TOOL_IDS
    # feat-333 M1 replaced bash_risk_gate with the unified auto_mode_gate classifier.
    assert "auto_mode_gate" in local_coding_hooks.DEFAULT_HOOK_MODULES


def test_personal_assistant_profile_exists() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.product_id == "personal_assistant"


def test_personal_assistant_profile_global_config_home() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.global_config_home == Path("~/.nanoassistant")


def test_personal_assistant_profile_workspace_config_dirname() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.workspace_config_dirname == ".nanoassistant"


def test_personal_assistant_profile_session_db_filename() -> None:
    assert PERSONAL_ASSISTANT_PROFILE.session_db_filename == "sessions.sqlite3"


def test_personal_assistant_package_exports_default_modules() -> None:
    assert personal_assistant_defaults.CONFIG_NAMESPACE == "nanoassistant"
    # prompts.py deleted; default_system_prompt="" signals segment assembly
    assert PERSONAL_ASSISTANT_PROFILE.default_system_prompt == ""
    assert {"read", "write", "edit", "bash", "agent", "web_fetch", "web_search"} <= set(personal_assistant_toolsets.DEFAULT_TOOL_IDS)
    assert set(personal_assistant_toolsets.OPTIONAL_TOOL_IDS) == {"send_message"}
    assert set(PERSONAL_ASSISTANT_PROFILE.optional_tool_ids) == {"send_message"}
    # feat-379-M1: communication_context is no longer a hook module — group context
    # is assembled by the pa.communication_context segment (prompt_sections.py).
    assert "communication_context" not in personal_assistant_hooks.DEFAULT_HOOK_MODULES
    assert "default_status" in personal_assistant_hooks.DEFAULT_HOOK_MODULES



def test_personal_assistant_bootstrap_loads_communication_context_hook(tmp_path: Path) -> None:
    # feat-379-M1: communication_context.setup() no longer registers a
    # before_agent_start prompt-injection handler.  The hook file is still
    # loaded (module stem present in module_stems) because the module itself
    # exists, but it registers no handlers for before_agent_start.
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)

    module_stems = {
        Path(handler.file_path).stem
        for handler in resolved.hook_registry.all_handlers()
        if handler.file_path is not None
    }

    # The communication_context module no longer registers hooks in M1 (setup=pass),
    # so its stem is absent from module_stems. default_status remains.
    assert "default_status" in module_stems
    # Verify the prompt injection was not added as before_agent_start.
    before_start_handlers = [
        h for h in resolved.hook_registry.all_handlers()
        if h.event == "before_agent_start"
        and h.file_path is not None
        and Path(h.file_path).stem == "communication_context"
    ]
    assert not before_start_handlers, (
        "feat-379-M1: communication_context must not register before_agent_start "
        "prompt injection — group context is now via pa.communication_context segment"
    )


def test_personal_assistant_hook_group_context_now_via_segment(tmp_path: Path) -> None:
    """feat-379-M1: group chat context comes from segment assembly, not hook.

    Replaces the retired test_personal_assistant_hook_uses_session_system_prompt_as_base.
    Verifies that the pa.communication_context segment correctly renders
    [Communication Context] for group scenarios.
    """
    from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
    from agent.products.personal_assistant.prompt_sections import PA_SECTIONS
    from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS

    ctx = PromptContext(
        available_tools=(),
        available_skills=(),
        current_datetime="2026-01-01T00:00:00",
        cwd="/workspace",
        memory_block=None,
        flags={},
        scenario={
            "conversation_type": "group",
            "agent_id": "agent-a",
            "participant_agent_ids": ["agent-a", "agent-b"],
        },
        vars={},
    )
    result = assemble_system_prompt(list(CORE_SECTIONS) + list(PA_SECTIONS), ctx)
    assert "[Communication Context]" in result
    assert "session_type: group" in result
    assert "your_agent_id: agent-a" in result



def test_platform_products_shims_export_canonical_profiles() -> None:
    assert LEGACY_LOCAL_CODING_PROFILE is LOCAL_CODING_PROFILE
    assert LEGACY_PERSONAL_ASSISTANT_PROFILE is PERSONAL_ASSISTANT_PROFILE
