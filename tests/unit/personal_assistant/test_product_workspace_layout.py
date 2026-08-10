"""PA factory wiring for the product-owned workspace layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from personal_assistant import product


def test_pa_kernel_passes_product_workspace_and_global_roots(
    tmp_path: Path, monkeypatch
) -> None:
    """PA selects .nanoassistant for both workspace and global configuration."""
    captured: dict[str, Any] = {}
    sentinel = object()

    def _build_kernel(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(product, "build_kernel", _build_kernel)

    assert (
        product.build_pa_kernel(
            llm=object(),  # type: ignore[arg-type]
            cron_services={},
            repo_root=tmp_path,
        )
        is sentinel
    )
    assert captured["workspace_config_dirname"] == ".nanoassistant"
    assert captured["workspace_skill_dirnames"] == (
        ".nanoassistant",
        ".claude",
        ".codex",
    )
    assert captured["skill_search_roots"] == (
        Path("~/.nanoassistant/skills"),
        Path("~/.claude/skills"),
        Path("~/.codex/skills"),
    )
    assert captured["global_config_root"] == Path("~/.nanoassistant")
