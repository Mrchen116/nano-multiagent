"""Workspace seeding behavior for persistent memory inputs."""

from __future__ import annotations

from pathlib import Path
def test_local_store_seeds_memory_in_config_subdir(tmp_path: Path) -> None:
    """Seed memory inputs in the product config directory, not workspace root."""
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
