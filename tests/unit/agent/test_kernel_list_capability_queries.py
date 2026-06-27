"""Unit tests for Kernel.list_* capability queries (refactor-406 决策 4).

list_models / list_tools / list_features / list_skills are kernel-side neutral
fact producers returning SDK-owned DTOs. These tests pin: the DTO shape, that
list_features reports only the two kernel-general features (not product toggles),
and that list_skills resolves per-workspace without cross-workspace mixing.

Built through the (current, expansion-era) build_kernel with a fake LLM client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent.sdk import LLMConfig, build_kernel
from agent.sdk.dto import FeatureInfo, ModelInfo, SkillInfo, ToolInfo


def _fake_llm_client() -> Any:
    class _FakeClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            async def _gen():
                if False:  # pragma: no cover - empty async generator
                    yield None

            return _gen()

    return _FakeClient()


def _kernel(tmp_path: Path):
    # refactor-406-M1 R7: built via the 2-layer surface (legacy product_profile path
    # removed). memory/skill_manage are kernel built-ins auto-registered by build_kernel
    # (决策 3) — not supplied here; list_features' tool-presence gating and list_skills
    # resolve under <workspace>/.nanocode/skills via the threaded workspace_config_dirname.
    return build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
            default_model="codex_oauth:gpt-5.5",
        ),
        workspace_config_dirname=".nanocode",
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )


def test_list_tools_returns_toolinfo_dtos(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    try:
        tools = kernel.list_tools()
        assert tools, "expected a non-empty tool catalog"
        assert all(isinstance(t, ToolInfo) for t in tools)
        # Names are non-empty strings; descriptions are strings.
        assert all(isinstance(t.name, str) and t.name for t in tools)
        assert all(isinstance(t.description, str) for t in tools)
    finally:
        kernel.close()


def test_list_features_reports_only_kernel_general_features(tmp_path: Path) -> None:
    """list_features must report exactly the two kernel-general features.

    Product toggles (heartbeat / cron_scheduling) are an application-layer
    projection, not kernel features (决策 3) — they must NOT appear here.
    """
    kernel = _kernel(tmp_path)
    try:
        features = kernel.list_features()
        assert all(isinstance(f, FeatureInfo) for f in features)
        keys = {f.key for f in features}
        assert keys == {"memory_curation", "skill_creation"}, (
            f"kernel features must be exactly the two general ones; got {keys}"
        )
        by_key = {f.key: f for f in features}
        assert by_key["memory_curation"].requires_tool == "memory"
        assert by_key["skill_creation"].requires_tool == "skill_manage"
        assert by_key["memory_curation"].default_on is True
    finally:
        kernel.close()


def test_list_models_returns_modelinfo_with_active_default(tmp_path: Path) -> None:
    """With no registry installed (test path), list_models falls back to active model."""
    kernel = _kernel(tmp_path)
    try:
        models = kernel.list_models()
        assert all(isinstance(m, ModelInfo) for m in models)
        # At least the active model is present and flagged default.
        assert any(m.is_default for m in models)
        assert any(m.name == "codex_oauth:gpt-5.5" for m in models)
    finally:
        kernel.close()


def test_list_skills_resolves_per_workspace_no_mixing(tmp_path: Path) -> None:
    """Two workspaces with different skills must not bleed into each other (决策 4)."""
    # LOCAL_CODING_PROFILE binds a config_resolver, so per-workspace skills live
    # under <workspace>/.nanocode/skills. Global skills (~/.nanocode/skills) may
    # also appear in BOTH lists — that's fine; the contract under test is that a
    # skill placed only in ws_a never appears in ws_b's list and vice versa.
    ws_a = tmp_path / "ws_a"
    ws_b = tmp_path / "ws_b"
    for ws, skill_name in ((ws_a, "alpha_skill"), (ws_b, "beta_skill")):
        skill_dir = ws / ".nanocode" / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: {skill_name} desc\n---\nbody\n",
            encoding="utf-8",
        )

    kernel = _kernel(tmp_path)
    try:
        a = kernel.list_skills(workspace_root=ws_a)
        b = kernel.list_skills(workspace_root=ws_b)
        assert all(isinstance(s, SkillInfo) for s in a + b)
        a_names = {s.name for s in a}
        b_names = {s.name for s in b}
        assert "alpha_skill" in a_names
        assert "beta_skill" in b_names
        assert "beta_skill" not in a_names, "cross-workspace skill leak (ws_a)"
        assert "alpha_skill" not in b_names, "cross-workspace skill leak (ws_b)"
    finally:
        kernel.close()


def test_list_skills_carries_skill_md_location(tmp_path: Path) -> None:
    """feat-430: each SkillInfo exposes its SKILL.md location so consumers can
    distinguish same-named skills living at different paths (Q7)."""
    ws = tmp_path / "ws"
    skill_dir = ws / ".nanocode" / "skills" / "located_skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: located_skill\ndescription: located desc\n---\nbody\n",
        encoding="utf-8",
    )

    kernel = _kernel(tmp_path)
    try:
        skills = kernel.list_skills(workspace_root=ws)
        located = next(s for s in skills if s.name == "located_skill")
        assert located.location is not None
        assert located.location.endswith("located_skill/SKILL.md")
    finally:
        kernel.close()
