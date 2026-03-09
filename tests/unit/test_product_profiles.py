"""Unit tests for product profile path field values.

Verifies that LOCAL_CODING_PROFILE and PERSONAL_ASSISTANT_PROFILE declare
the correct path fields per M75 architecture spec.
"""

from pathlib import Path

from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE


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


def test_personal_assistant_profile_exists() -> None:
    from nano_multiagent.platform.products.personal_assistant import (
        PERSONAL_ASSISTANT_PROFILE,
    )

    assert PERSONAL_ASSISTANT_PROFILE.product_id == "personal_assistant"


def test_personal_assistant_profile_global_config_home() -> None:
    from nano_multiagent.platform.products.personal_assistant import (
        PERSONAL_ASSISTANT_PROFILE,
    )

    assert PERSONAL_ASSISTANT_PROFILE.global_config_home == Path("~/.nanoassistant")


def test_personal_assistant_profile_workspace_config_dirname() -> None:
    from nano_multiagent.platform.products.personal_assistant import (
        PERSONAL_ASSISTANT_PROFILE,
    )

    assert PERSONAL_ASSISTANT_PROFILE.workspace_config_dirname == ".nanoassistant"


def test_personal_assistant_profile_session_db_filename() -> None:
    from nano_multiagent.platform.products.personal_assistant import (
        PERSONAL_ASSISTANT_PROFILE,
    )

    assert PERSONAL_ASSISTANT_PROFILE.session_db_filename == "sessions.sqlite3"
