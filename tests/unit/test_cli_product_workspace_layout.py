"""CLI factory wiring for the product-owned workspace layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from coding_cli import product


def test_cli_kernel_passes_product_workspace_and_global_roots(
    tmp_path: Path, monkeypatch
) -> None:
    """CLI selects .nanocode for both workspace and global configuration."""
    captured: dict[str, Any] = {}
    sentinel = object()

    def _build_kernel(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(product, "build_kernel", _build_kernel)

    assert (
        product.build_cli_kernel(
            llm=object(),  # type: ignore[arg-type]
            can_use_tool=object(),
            repo_root=tmp_path,
        )
        is sentinel
    )
    assert captured["workspace_config_dirname"] == ".nanocode"
    assert captured["workspace_skill_dirnames"] == (
        ".nanocode",
        ".claude",
        ".codex",
    )
    assert captured["skill_search_roots"] == (
        Path("~/.nanocode/skills"),
        Path("~/.claude/skills"),
        Path("~/.codex/skills"),
    )
    assert captured["global_config_root"] == Path("~/.nanocode")
