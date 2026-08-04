"""Behavioral tests for workspace skill resolver construction."""

from pathlib import Path

from agent.core.skills import make_skill_resolver


def test_make_skill_resolver_prefers_workspace_before_extra_roots(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    extra = tmp_path / "extra_skills"
    extra.mkdir()

    resolver = make_skill_resolver(
        workspace_root=workspace,
        workspace_config_dirname=".nanoassistant",
        skill_search_roots=(extra,),
    )

    assert resolver is not None
    assert resolver.user_skill_roots() == (
        (workspace / ".nanoassistant" / "skills").resolve(),
        extra.resolve(),
    )


def test_make_skill_resolver_is_disabled_without_config_dirname(
    tmp_path: Path,
) -> None:
    resolver = make_skill_resolver(
        workspace_root=tmp_path,
        workspace_config_dirname=None,
        skill_search_roots=(),
    )

    assert resolver is None
