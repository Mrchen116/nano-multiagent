"""Tests for ConfigResolver.user_memory_root() — new method added in feat-349-M2."""

from pathlib import Path

import pytest

from agent.platform.config.resolver import ConfigResolver
from agent.products.base import ProductProfile


def _make_profile(
    *,
    global_config_home: Path | None = None,
    workspace_config_dirname: str = ".testproduct",
) -> ProductProfile:
    return ProductProfile(
        product_id="test_product",
        display_name="Test Product",
        config_namespace="testproduct",
        global_config_home=global_config_home or Path("~/.testproduct"),
        workspace_config_dirname=workspace_config_dirname,
    )


def test_user_memory_root_with_workspace(tmp_path: Path) -> None:
    """user_memory_root returns workspace/<dirname>/memory when workspace is set."""
    profile = _make_profile(workspace_config_dirname=".testproduct")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    result = resolver.user_memory_root()
    assert result is not None
    assert result == tmp_path / ".testproduct" / "memory"


def test_user_memory_root_without_workspace() -> None:
    """user_memory_root returns None when no workspace is configured."""
    profile = _make_profile()
    resolver = ConfigResolver(profile=profile)
    result = resolver.user_memory_root()
    assert result is None


def test_user_memory_root_no_workspace_config_dirname(tmp_path: Path) -> None:
    """user_memory_root returns None when workspace_config_dirname is empty."""
    profile = ProductProfile(
        product_id="noop",
        display_name="Noop",
        config_namespace="noop",
        workspace_config_dirname=None,
    )
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    result = resolver.user_memory_root()
    assert result is None


def test_user_memory_root_is_absolute_path(tmp_path: Path) -> None:
    """The returned path is always absolute."""
    profile = _make_profile(workspace_config_dirname=".myproduct")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    result = resolver.user_memory_root()
    assert result is not None
    assert result.is_absolute()


def test_user_memory_root_pa_profile(tmp_path: Path) -> None:
    """Smoke test with PA-like config (.nanoassistant)."""
    profile = ProductProfile(
        product_id="personal_assistant",
        display_name="Personal Assistant",
        config_namespace="pa",
        global_config_home=Path("~/.nanoassistant"),
        workspace_config_dirname=".nanoassistant",
    )
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    result = resolver.user_memory_root()
    assert result == tmp_path / ".nanoassistant" / "memory"


def test_user_memory_root_lc_profile(tmp_path: Path) -> None:
    """Smoke test with LC-like config (.nanocode)."""
    profile = ProductProfile(
        product_id="local_coding",
        display_name="Local Coding",
        config_namespace="lc",
        global_config_home=Path("~/.nanocode"),
        workspace_config_dirname=".nanocode",
    )
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    result = resolver.user_memory_root()
    assert result == tmp_path / ".nanocode" / "memory"
