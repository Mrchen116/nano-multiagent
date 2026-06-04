"""Unit tests for memory prompt section wiring and workspace seeding.

Validates:
- core.memory_guidance segment is in CORE_SECTIONS
- PA ensure_workspace_defaults seeds MEMORY.md and USER.md under the
  product config subdir (.nanoassistant/memory/), not at workspace root
"""

from __future__ import annotations

from pathlib import Path


def test_core_memory_guidance_still_present() -> None:
    """core.memory_guidance must remain in CORE_SECTIONS as the replacement for pa.memory_intro."""
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
    # Must NOT be seeded at workspace root — only under the product config subdir.
    assert not (workspace / "MEMORY.md").exists(), (
        "MEMORY.md must NOT be at workspace root: "
        "seeding there would collide across products sharing the same workspace"
    )
