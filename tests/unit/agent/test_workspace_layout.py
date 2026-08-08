"""Workspace layout boundary validation."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from agent.core.workspace import WorkspaceLayout
from tests.unit.agent._workspace_scope_support import kernel as make_kernel


@pytest.mark.parametrize("dirname", (".", ".."))
def test_workspace_layout_rejects_dot_path_segments(
    tmp_path: Path, dirname: str
) -> None:
    """A product state directory cannot alias the workspace or its parent."""

    with pytest.raises(ValueError, match="dot-prefixed name"):
        WorkspaceLayout(workspace_root=tmp_path, config_dirname=dirname)


@pytest.mark.asyncio
async def test_kernel_normalizes_workspace_config_dirname_before_session_storage(
    tmp_path: Path,
) -> None:
    """The durable session path and execution scope share one normalized dirname."""

    workspace = tmp_path / "workspace"
    live_kernel = make_kernel(
        workspace,
        workspace_config_dirname=" .consumer ",
    )
    try:
        session = await live_kernel.create_session(workspace_root=workspace)
        assert live_kernel._workspace_config_dirname == ".consumer"  # noqa: SLF001
        assert (
            workspace / ".consumer" / "sessions" / f"{session.session_id}.jsonl"
        ).is_file()
        assert not (workspace / " .consumer ").exists()
    finally:
        live_kernel.close()


@pytest.mark.parametrize("dirname", ("", ".", ".."))
def test_kernel_rejects_invalid_workspace_dir_before_durable_storage(
    tmp_path: Path, dirname: str
) -> None:
    """Invalid public SDK input cannot create root or parent session artifacts."""

    workspace = tmp_path / "workspace"
    parent_sessions = tmp_path / "sessions"
    with pytest.raises(ValueError, match="dot-prefixed name"):
        make_kernel(workspace, workspace_config_dirname=dirname)
    assert not (workspace / "sessions").exists()
    assert not parent_sessions.exists()


@pytest.mark.asyncio
async def test_kernel_rejects_malformed_workspace_policy_before_session_storage(
    tmp_path: Path,
) -> None:
    """An invalid selected policy never leaves an unusable session transcript."""

    workspace = tmp_path / "workspace"
    policy = workspace / ".consumer" / "policy.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text("[bash\n", encoding="utf-8")
    live_kernel = make_kernel(workspace, workspace_config_dirname=".consumer")
    try:
        with pytest.raises(tomllib.TOMLDecodeError):
            await live_kernel.create_session(workspace_root=workspace)
        assert not (workspace / ".consumer" / "sessions").exists()
    finally:
        live_kernel.close()
