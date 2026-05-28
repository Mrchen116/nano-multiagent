"""Unit tests for R6 cleanup: old f-string templates deleted, pa.memory_intro removed.

Validates:
- products/{personal_assistant,local_coding}/prompts.py no longer exist
- pa.memory_intro segment is NOT in PA_SECTIONS
- core.memory_guidance is in CORE_SECTIONS (still present as replacement)
- local_store.py seeds MEMORY.md and USER.md under .nanoassistant/memory/
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_local_coding_prompts_file_deleted() -> None:
    """products/local_coding/prompts.py must not exist."""
    import agent.products.local_coding as lc_pkg
    pkg_dir = Path(lc_pkg.__file__).parent
    prompts_file = pkg_dir / "prompts.py"
    assert not prompts_file.exists(), (
        "products/local_coding/prompts.py should be deleted (decision 11)"
    )


def test_personal_assistant_prompts_file_deleted() -> None:
    """products/personal_assistant/prompts.py must not exist."""
    import agent.products.personal_assistant as pa_pkg
    pkg_dir = Path(pa_pkg.__file__).parent
    prompts_file = pkg_dir / "prompts.py"
    assert not prompts_file.exists(), (
        "products/personal_assistant/prompts.py should be deleted (decision 11)"
    )


def test_pa_memory_intro_segment_removed() -> None:
    """pa.memory_intro must NOT be in PA_SECTIONS after R6."""
    from agent.products.personal_assistant.prompt_sections import PA_SECTIONS
    names = {s.name for s in PA_SECTIONS}
    assert "pa.memory_intro" not in names, (
        "pa.memory_intro segment should be deleted (decision 7)"
    )


def test_core_memory_guidance_still_present() -> None:
    """core.memory_guidance must remain in CORE_SECTIONS as replacement."""
    from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS
    names = {s.name for s in CORE_SECTIONS}
    assert "core.memory_guidance" in names


def test_local_store_seeds_memory_in_config_subdir(tmp_path: Path) -> None:
    """PA ensure_workspace_defaults seeds MEMORY.md under <workspace>/.nanoassistant/memory/."""
    from personal_assistant.config.local_store import ensure_workspace_defaults

    workspace = tmp_path / "agent-workspace"
    workspace.mkdir()
    ensure_workspace_defaults(workspace)

    memory_dir = workspace / ".nanoassistant" / "memory"
    assert (memory_dir / "MEMORY.md").exists(), (
        f"MEMORY.md should be seeded under {memory_dir}"
    )
    assert (memory_dir / "USER.md").exists(), (
        f"USER.md should be seeded under {memory_dir}"
    )
    # Must NOT be seeded at workspace root (decision 14)
    assert not (workspace / "MEMORY.md").exists(), (
        "MEMORY.md must NOT be at workspace root"
    )
