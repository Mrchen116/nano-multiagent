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
from agent.products.local_coding import prompts as local_coding_prompts
from agent.products.local_coding import toolsets as local_coding_toolsets
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE
from agent.products.personal_assistant import defaults as personal_assistant_defaults
from agent.products.personal_assistant import hooks as personal_assistant_hooks
from agent.products.personal_assistant import prompts as personal_assistant_prompts
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
    assert local_coding_prompts.LOCAL_CODING_SYSTEM_PROMPT == LOCAL_CODING_PROFILE.default_system_prompt
    assert {"read", "write", "edit", "bash", "agent", "task_stop"} <= set(local_coding_toolsets.DEFAULT_TOOL_IDS)
    assert "skill_manage" in local_coding_toolsets.DEFAULT_TOOL_IDS
    assert "memory" in local_coding_toolsets.DEFAULT_TOOL_IDS
    assert "bash_risk_gate" in local_coding_hooks.DEFAULT_HOOK_MODULES


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
    assert (
        personal_assistant_prompts.PERSONAL_ASSISTANT_SYSTEM_PROMPT
        == PERSONAL_ASSISTANT_PROFILE.default_system_prompt
    )
    assert {"read", "write", "edit", "bash", "agent", "web_fetch", "web_search"} <= set(personal_assistant_toolsets.DEFAULT_TOOL_IDS)
    assert set(personal_assistant_toolsets.OPTIONAL_TOOL_IDS) == {"send_message"}
    assert set(PERSONAL_ASSISTANT_PROFILE.optional_tool_ids) == {"send_message"}
    assert "communication_context" in personal_assistant_hooks.DEFAULT_HOOK_MODULES
    assert "default_status" in personal_assistant_hooks.DEFAULT_HOOK_MODULES



def test_personal_assistant_bootstrap_loads_communication_context_hook(tmp_path: Path) -> None:
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)

    module_stems = {
        Path(handler.file_path).stem
        for handler in resolved.hook_registry.all_handlers()
        if handler.file_path is not None
    }

    assert "communication_context" in module_stems
    assert "default_status" in module_stems



def test_personal_assistant_hook_uses_session_system_prompt_as_base() -> None:
    registry = HookRegistry()
    personal_assistant_hooks.setup(
        HookAPI(registry, source="product", module_name="pa_hooks", file_path=None)
    )

    handlers = registry.handlers_for("before_agent_start")
    assert handlers

    result = handlers[0].handler(
        {"message": "hello", "system_prompt": None},
        HookContext(
            session_id="sess-test",
            metadata={
                "conversation_type": "group",
                "agent_id": "agent-a",
                "participant_agent_ids": ["agent-a", "agent-b"],
                "system_prompt": "You are agent-a.",
            },
        ),
    )

    assert result is not None
    assert result["system_prompt"].startswith("You are agent-a.")
    assert "[Communication Context]" in result["system_prompt"]
    assert "group_participants: agent-a, agent-b" in result["system_prompt"]



def test_platform_products_shims_export_canonical_profiles() -> None:
    assert LEGACY_LOCAL_CODING_PROFILE is LOCAL_CODING_PROFILE
    assert LEGACY_PERSONAL_ASSISTANT_PROFILE is PERSONAL_ASSISTANT_PROFILE
