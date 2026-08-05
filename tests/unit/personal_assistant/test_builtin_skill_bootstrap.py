from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tomllib
from types import SimpleNamespace

import pytest

from agent.core.skills.registry import SkillRegistry
from agent.platform.tools.builtins.skill_view import SkillViewTool
from agent.sdk import LLMConfig
from personal_assistant.builtin_skills import bootstrap as builtin_skill_bootstrap
from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from personal_assistant.config.local_store import load_local_config
from personal_assistant.product import build_pa_kernel, prompt_for
from personal_assistant.reporter.upstream_reporter import (
    build_agent_capabilities_payload,
    build_runtime_capabilities,
)


_PRODUCT_DOCS_SKILL = "nanoassistant-docs"


@pytest.mark.parametrize(
    "skill_name", ["lark-doc", "lark-shared", "conversation-skill-distiller"]
)
def test_install_builtin_skills_copies_missing_skill(
    tmp_path: Path,
    skill_name: str,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    target = target_root / skill_name / "SKILL.md"
    assert target.is_file()
    assert installed[skill_name] == target


@pytest.mark.parametrize("skill_name", ["lark-doc", "conversation-skill-distiller"])
def test_install_builtin_skills_replaces_managed_skill_directory(
    tmp_path: Path,
    skill_name: str,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = target_root / skill_name / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("stale managed skill\n", encoding="utf-8")
    stale_file = skill_file.parent / "removed-in-current-package.md"
    stale_file.write_text("stale\n", encoding="utf-8")

    installed = install_builtin_skills(target_root=target_root)

    assert installed[skill_name] == skill_file
    assert skill_file.read_text(encoding="utf-8") != "stale managed skill\n"
    assert not stale_file.exists()


def test_install_builtin_skills_preserves_non_builtin_user_skill(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = target_root / "my-custom-skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("user-owned skill\n", encoding="utf-8")

    install_builtin_skills(target_root=target_root)

    assert skill_file.read_text(encoding="utf-8") == "user-owned skill\n"


def test_install_builtin_skills_restores_failed_switch_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    failed_name = "conversation-skill-distiller"
    failed_skill = target_root / failed_name / "SKILL.md"
    failed_skill.parent.mkdir(parents=True)
    failed_skill.write_text("old complete skill\n", encoding="utf-8")
    failed_extra = failed_skill.parent / "old-extra.md"
    failed_extra.write_text("old extra\n", encoding="utf-8")
    succeeding_skill = target_root / "lark-doc" / "SKILL.md"
    succeeding_skill.parent.mkdir(parents=True)
    succeeding_skill.write_text("old lark skill\n", encoding="utf-8")
    real_replace = Path.replace
    failed_once = False

    def fail_one_staging_switch(path: Path, target: Path | str) -> Path:
        nonlocal failed_once
        if not failed_once and path.name.startswith(f".{failed_name}.staging-"):
            failed_once = True
            raise OSError("injected switch failure")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_one_staging_switch)
    caplog.set_level("WARNING", logger=builtin_skill_bootstrap.__name__)

    installed = install_builtin_skills(target_root=target_root)

    assert failed_once
    assert failed_name not in installed
    assert failed_skill.read_text(encoding="utf-8") == "old complete skill\n"
    assert failed_extra.read_text(encoding="utf-8") == "old extra\n"
    assert installed["lark-doc"] == succeeding_skill
    assert succeeding_skill.read_text(encoding="utf-8") != "old lark skill\n"
    assert failed_name in caplog.text
    assert "injected switch failure" in caplog.text


def test_install_builtin_skills_keeps_failed_backup_cleanup_out_of_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = target_root / _PRODUCT_DOCS_SKILL / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text(
        "---\n"
        f"name: {_PRODUCT_DOCS_SKILL}\n"
        "description: old product manual\n"
        "---\n\n"
        "old product manual\n",
        encoding="utf-8",
    )
    real_remove_path = builtin_skill_bootstrap._remove_path
    cleanup_failed = False

    def fail_backup_cleanup(path: Path) -> None:
        nonlocal cleanup_failed
        if not cleanup_failed and ".backup-" in path.name:
            cleanup_failed = True
            raise OSError("injected backup cleanup failure")
        real_remove_path(path)

    monkeypatch.setattr(builtin_skill_bootstrap, "_remove_path", fail_backup_cleanup)
    caplog.set_level("WARNING", logger=builtin_skill_bootstrap.__name__)

    installed = install_builtin_skills(target_root=target_root)

    discovered = {
        skill.name: skill
        for skill in SkillRegistry(search_roots=(target_root,)).list_skills()
    }
    assert cleanup_failed
    assert installed[_PRODUCT_DOCS_SKILL] == skill_file
    assert discovered[_PRODUCT_DOCS_SKILL].location == skill_file.resolve()
    assert "old product manual" not in discovered[_PRODUCT_DOCS_SKILL].description
    assert "injected backup cleanup failure" in caplog.text


def test_install_builtin_skills_holds_one_root_lock_while_switching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    real_sync = builtin_skill_bootstrap._sync_skill_directory
    lock_held = False
    locked_roots: list[Path] = []
    synchronized_names: list[str] = []

    @contextmanager
    def observe_root_lock(destination_root: Path):
        nonlocal lock_held
        assert not lock_held
        lock_held = True
        locked_roots.append(destination_root)
        try:
            yield
        finally:
            lock_held = False

    def assert_locked_sync(*, source: Path, destination: Path) -> None:
        assert lock_held
        synchronized_names.append(destination.name)
        real_sync(source=source, destination=destination)

    monkeypatch.setattr(
        builtin_skill_bootstrap, "_builtin_skill_sync_lock", observe_root_lock
    )
    monkeypatch.setattr(
        builtin_skill_bootstrap, "_sync_skill_directory", assert_locked_sync
    )

    install_builtin_skills(target_root=target_root)

    assert locked_roots == [target_root]
    assert {_PRODUCT_DOCS_SKILL, "lark-doc"} <= set(synchronized_names)


def test_builtin_skills_are_included_as_package_data() -> None:
    pyproject_path = Path(__file__).parents[3] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_data = payload["tool"]["setuptools"]["package-data"]

    assert "builtin_skills/**" in package_data["personal_assistant"]


def test_packaged_lark_bundle_matches_its_manifest_and_gateway_boundaries() -> None:
    """The packaged snapshot remains complete and keeps its two PA adaptations."""
    package_root = (
        Path(__file__).parents[3] / "src" / "personal_assistant" / "builtin_skills"
    )
    packaged_names = {
        path.name
        for path in package_root.glob("lark-*")
        if (path / "SKILL.md").is_file()
    }

    assert packaged_names == set(lark_skill_names())
    assert len(lark_skill_names()) == len(set(lark_skill_names()))
    assert "../lark-shared/SKILL.md" in (
        package_root / "lark-doc" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Gateway-bound Feishu conversations" in (
        package_root / "lark-im" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Gateway-bound Feishu conversations" in (
        package_root / "lark-event" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_install_builtin_skills_installs_the_complete_lark_bundle(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    assert set(lark_skill_names()) <= set(installed)
    assert all(
        (target_root / skill_id / "SKILL.md").is_file()
        for skill_id in lark_skill_names()
    )


_LLM_YAML = """\
llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
"""


def test_installed_builtin_skills_are_visible_to_capabilities_and_skill_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    install_builtin_skills(target_root=home / ".nanoassistant" / "skills")
    workspace = tmp_path / "agent-ws"
    workspace.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: feishu-agent",
                f"    workspace_root: {workspace}",
            ]
        )
        + "\n"
        + _LLM_YAML,
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    kernel = build_pa_kernel(
        llm=LLMConfig.from_payload(config.llm),
        cron_services={},
        repo_root=tmp_path / "repo",
    )
    try:
        node_skills = {
            item["name"]: item for item in build_runtime_capabilities(kernel).skills
        }
        agent_names = {
            item["name"]
            for item in build_agent_capabilities_payload(
                kernel,
                workspace_root=str(workspace),
            )["skills"]
        }
        discovered_names = {
            skill.name for skill in kernel.list_skills(workspace_root=workspace)
        }
        preview = kernel.assemble_prompt_preview(
            workspace_root=workspace,
            skill_ids=[_PRODUCT_DOCS_SKILL],
            prompt=prompt_for(config.agents[0]),
            enabled_tools=["skill_view"],
        )

        assert "lark-doc" in node_skills
        assert _PRODUCT_DOCS_SKILL in node_skills
        assert node_skills[_PRODUCT_DOCS_SKILL]["default_on"] is True
        assert "lark-doc" in agent_names
        assert _PRODUCT_DOCS_SKILL in agent_names
        assert {"lark-doc", "lark-shared", _PRODUCT_DOCS_SKILL} <= discovered_names
        assert f"<name>{_PRODUCT_DOCS_SKILL}</name>" in preview["prompt"]
    finally:
        kernel.close()

    skill_root = home / ".nanoassistant" / "skills"
    manual_path = skill_root / _PRODUCT_DOCS_SKILL / "SKILL.md"
    manual = manual_path.read_text(encoding="utf-8")
    tool = SkillViewTool(
        skill_root=skill_root,
        registry=SkillRegistry(search_roots=(skill_root,)),
    )
    result = tool.run(
        {"name": _PRODUCT_DOCS_SKILL},
        SimpleNamespace(
            session_id="product-docs-session",
            tool_call_id="product-docs-call",
            session_metadata={"skills": [_PRODUCT_DOCS_SKILL]},
        ),
    )

    assert result["success"] is True
    assert result["content"] == manual
    assert "# Nano Personal Assistant 产品手册" in manual
    assert "## Heartbeat 与 Cron" in manual
    assert "## 故障排查" in manual
    assert len(tool.serialize_result(result)) < tool.max_result_size_chars
