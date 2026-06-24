"""Regression: runtime skill resolution == preview/list_skills (bugfix-431 决策 2/3).

Root cause of the original bug: AgentRuntime had no resolver injected at build
time, so runtime skill resolution fell through to default_skill_search_roots
(Codex-only roots), while Kernel.list_skills / assemble_prompt_preview used a
per-workspace _WorkspaceDirnameSkillResolver.  A PA agent with 12 skills in
<workspace>/.nanoassistant/skills would show all 12 in preview but only
~/.codex/skills (1 skill) at runtime.

These tests assert the now-fixed invariants:
  1. list_skills and runtime.resolve_available_skills return the same skill set.
  2. Skills placed in <workspace>/<dirname>/skills are visible to runtime (the
     original bug: they were NOT visible before bugfix-431).
  3. An extra deployment-level root is visible through both paths equally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdk import LLMConfig, build_kernel


def _fake_llm_client() -> Any:
    class _FakeClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            async def _gen():
                if False:  # pragma: no cover - empty async generator
                    yield None

            return _gen()

    return _FakeClient()


def _kernel(tmp_path: Path, *, workspace_config_dirname: str = ".testconfig", extra_roots: tuple[Path, ...] = ()):
    return build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
            default_model="codex_oauth:gpt-5.5",
        ),
        workspace_config_dirname=workspace_config_dirname,
        repo_root=tmp_path,
        skill_search_roots=list(extra_roots),
        _llm_client_override=_fake_llm_client(),
    )


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} desc\n---\nbody\n",
        encoding="utf-8",
    )


def test_runtime_sees_same_skills_as_list_skills(tmp_path: Path) -> None:
    """Core regression: runtime resolution == list_skills for workspace dirname skills.

    Before bugfix-431, runtime used no resolver (Codex-only fallback) while
    list_skills used _WorkspaceDirnameSkillResolver.  After the fix both go
    through make_skill_resolver with identical arguments.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()

    # Place two skills under the workspace config dirname — this is what was
    # invisible to runtime before bugfix-431.
    _write_skill(workspace / ".testconfig" / "skills", "alpha_skill")
    _write_skill(workspace / ".testconfig" / "skills", "beta_skill")

    kernel = _kernel(tmp_path, workspace_config_dirname=".testconfig")
    try:
        list_names = {s.name for s in kernel.list_skills(workspace_root=workspace)}
        # Access runtime via the internal components — same runtime that runs turns.
        runtime = kernel._c.runtime  # type: ignore[attr-defined]
        runtime_skills = runtime.resolve_available_skills(workspace)
        runtime_names = {s.name for s in runtime_skills}

        assert "alpha_skill" in list_names, "list_skills must see workspace-dirname skills"
        assert "beta_skill" in list_names

        # The central invariant: runtime and preview/list see the same set.
        assert runtime_names == list_names, (
            f"runtime resolution ({runtime_names}) differs from list_skills ({list_names}); "
            "bugfix-431 regression"
        )
    finally:
        kernel.close()


def test_runtime_resolves_workspace_skills_not_empty(tmp_path: Path) -> None:
    """Explicit original-bug scenario: workspace dirname skills are non-empty to runtime.

    The original bug produced an empty tuple from runtime (no resolver = no results
    from workspace dirname), while preview showed the full set.  This test asserts
    runtime returns a non-empty result when skills exist under the config dirname.
    """
    workspace = tmp_path / "ws"
    _write_skill(workspace / ".testconfig" / "skills", "ws_only_skill")

    kernel = _kernel(tmp_path, workspace_config_dirname=".testconfig")
    try:
        runtime = kernel._c.runtime  # type: ignore[attr-defined]
        runtime_skills = runtime.resolve_available_skills(workspace)
        runtime_names = {s.name for s in runtime_skills}

        assert "ws_only_skill" in runtime_names, (
            "bugfix-431 regression: runtime must resolve workspace-dirname skills; "
            "got empty — likely no resolver was injected into AgentRuntime"
        )
    finally:
        kernel.close()


def test_extra_deployment_root_visible_through_both_paths(tmp_path: Path) -> None:
    """Extra skill_search_roots are equally visible to list_skills and runtime."""
    workspace = tmp_path / "ws"
    workspace.mkdir()

    extra_root = tmp_path / "deployment_skills"
    _write_skill(extra_root, "shared_skill")

    kernel = _kernel(tmp_path, workspace_config_dirname=".testconfig", extra_roots=(extra_root,))
    try:
        list_names = {s.name for s in kernel.list_skills(workspace_root=workspace)}
        runtime = kernel._c.runtime  # type: ignore[attr-defined]
        runtime_names = {s.name for s in runtime.resolve_available_skills(workspace)}

        assert "shared_skill" in list_names, "list_skills must see extra deployment root"
        assert "shared_skill" in runtime_names, "runtime must see extra deployment root"
        assert runtime_names == list_names, (
            f"runtime ({runtime_names}) != list_skills ({list_names}) for extra root"
        )
    finally:
        kernel.close()


def test_include_names_filter_consistent_across_paths(tmp_path: Path) -> None:
    """include_names filter on runtime.resolve_available_skills is consistent with list_skills."""
    workspace = tmp_path / "ws"
    _write_skill(workspace / ".testconfig" / "skills", "wanted")
    _write_skill(workspace / ".testconfig" / "skills", "unwanted")

    kernel = _kernel(tmp_path, workspace_config_dirname=".testconfig")
    try:
        # list_skills has no include_names filter — it always returns all skills.
        # resolve_available_skills with include_names should be a subset of list_skills.
        all_names = {s.name for s in kernel.list_skills(workspace_root=workspace)}
        runtime = kernel._c.runtime  # type: ignore[attr-defined]
        filtered = runtime.resolve_available_skills(workspace, include_names=["wanted"])
        filtered_names = {s.name for s in filtered}

        assert "wanted" in all_names
        assert "unwanted" in all_names
        assert filtered_names == {"wanted"}, (
            f"filtered runtime resolution should contain only 'wanted'; got {filtered_names}"
        )
    finally:
        kernel.close()
