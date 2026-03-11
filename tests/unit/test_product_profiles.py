"""Unit tests for canonical product profile packages and path fields.

Verifies that LOCAL_CODING_PROFILE and PERSONAL_ASSISTANT_PROFILE live under
`agent.products.*` and declare the expected package-level defaults.
"""

from pathlib import Path

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
    assert set(local_coding_toolsets.DEFAULT_TOOL_IDS) == {"read", "write", "edit", "bash", "task"}
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
    assert set(personal_assistant_toolsets.DEFAULT_TOOL_IDS) == {"read", "task"}
    assert set(personal_assistant_toolsets.OPTIONAL_TOOL_IDS) == {"send_message"}
    assert set(PERSONAL_ASSISTANT_PROFILE.optional_tool_ids) == {"send_message"}
    assert "default_status" in personal_assistant_hooks.DEFAULT_HOOK_MODULES


def test_platform_products_shims_export_canonical_profiles() -> None:
    assert LEGACY_LOCAL_CODING_PROFILE is LOCAL_CODING_PROFILE
    assert LEGACY_PERSONAL_ASSISTANT_PROFILE is PERSONAL_ASSISTANT_PROFILE
