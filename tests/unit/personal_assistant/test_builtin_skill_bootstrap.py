from __future__ import annotations

from contextlib import contextmanager
import fcntl
import multiprocessing
import os
from pathlib import Path
import re
import tomllib
from types import SimpleNamespace
from typing import Any

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
_REFERENCE_LINK_PATTERN = re.compile(r"]\((references/[^)#?]+\.md)\)")


def _packaged_product_docs_root() -> Path:
    return (
        Path(__file__).parents[3]
        / "src"
        / "personal_assistant"
        / "builtin_skills"
        / _PRODUCT_DOCS_SKILL
    )


def _linked_reference_paths(manual: str) -> set[Path]:
    return {Path(target) for target in _REFERENCE_LINK_PATTERN.findall(manual)}


def _install_builtin_skills_process(
    target_root: str,
    attempted: Any,
    entered_switch: Any | None,
    release_switch: Any | None,
    outcomes: Any,
) -> None:
    attempted.set()
    if entered_switch is not None:
        real_sync = builtin_skill_bootstrap._sync_skill_directory
        first_switch = True

        def pause_first_switch(*, source: Path, destination: Path) -> None:
            nonlocal first_switch
            if first_switch:
                first_switch = False
                entered_switch.set()
                if release_switch is not None and not release_switch.wait(timeout=20):
                    raise TimeoutError("parent did not release first skill switch")
            real_sync(source=source, destination=destination)

        builtin_skill_bootstrap._sync_skill_directory = pause_first_switch

    try:
        installed = install_builtin_skills(target_root=target_root)
    except BaseException as exc:  # noqa: BLE001
        outcomes.put(("error", repr(exc)))
        raise
    outcomes.put(("ok", sorted(installed)))


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


@pytest.mark.parametrize(
    "skill_name",
    [_PRODUCT_DOCS_SKILL, "lark-doc", "conversation-skill-distiller"],
)
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


def test_install_builtin_skills_keeps_one_lock_scope_across_complete_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    real_sync = builtin_skill_bootstrap._sync_skill_directory
    lock_held = False
    lock_entries = 0
    synchronized_names: list[str] = []

    @contextmanager
    def observe_root_lock(destination_root: Path):
        nonlocal lock_held, lock_entries
        assert destination_root == target_root
        assert not lock_held
        lock_held = True
        lock_entries += 1
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

    assert lock_entries == 1
    assert {_PRODUCT_DOCS_SKILL, "lark-doc"} <= set(synchronized_names)


def test_install_builtin_skills_uses_real_cross_process_root_lock(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    stale_manual = target_root / _PRODUCT_DOCS_SKILL / "SKILL.md"
    stale_manual.parent.mkdir(parents=True)
    stale_manual.write_text("stale product manual\n", encoding="utf-8")
    context = multiprocessing.get_context("spawn")
    first_attempted = context.Event()
    first_entered_switch = context.Event()
    release_first_switch = context.Event()
    second_attempted = context.Event()
    second_entered_switch = context.Event()
    outcomes = context.Queue()
    first = context.Process(
        target=_install_builtin_skills_process,
        args=(
            str(target_root),
            first_attempted,
            first_entered_switch,
            release_first_switch,
            outcomes,
        ),
    )
    second = context.Process(
        target=_install_builtin_skills_process,
        args=(
            str(target_root),
            second_attempted,
            second_entered_switch,
            None,
            outcomes,
        ),
    )
    first.start()
    lock_fd: int | None = None
    try:
        assert first_attempted.wait(timeout=10)
        assert first_entered_switch.wait(timeout=20)
        lock_path = target_root / builtin_skill_bootstrap._SYNC_LOCK_FILENAME
        lock_fd = os.open(lock_path, os.O_RDWR)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            root_lock_is_held = True
        else:
            root_lock_is_held = False
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        assert root_lock_is_held

        second.start()
        assert second_attempted.wait(timeout=10)
        assert not second_entered_switch.wait(timeout=1)
    finally:
        release_first_switch.set()
        for process in (first, second):
            if process.pid is None:
                continue
            process.join(timeout=30)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        if lock_fd is not None:
            os.close(lock_fd)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert second_entered_switch.is_set()
    assert [outcomes.get(timeout=5)[0] for _ in range(2)] == ["ok", "ok"]
    assert stale_manual.read_text(encoding="utf-8") == (
        _packaged_product_docs_root() / "SKILL.md"
    ).read_text(encoding="utf-8")

    lock_fd = os.open(
        target_root / builtin_skill_bootstrap._SYNC_LOCK_FILENAME, os.O_RDWR
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


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
            enabled_tools=["skill_view", "read"],
        )

        assert {"skill_view", "read"} <= set(config.agents[0].tool_allowlist)
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
    manual_root = skill_root / _PRODUCT_DOCS_SKILL
    manual_path = manual_root / "SKILL.md"
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
    assert len(tool.serialize_result(result)) < tool.max_result_size_chars

    packaged_root = _packaged_product_docs_root()
    linked_references = _linked_reference_paths(manual)
    packaged_references = {
        path.relative_to(packaged_root)
        for path in (packaged_root / "references").rglob("*.md")
    }
    assert linked_references
    assert all(path.parent == Path("references") for path in linked_references)
    assert linked_references == packaged_references

    packaged_files = {
        path.relative_to(packaged_root)
        for path in packaged_root.rglob("*")
        if path.is_file()
    }
    installed_files = {
        path.relative_to(manual_root)
        for path in manual_root.rglob("*")
        if path.is_file()
    }
    assert installed_files == packaged_files
    for relative_path in packaged_files:
        assert (manual_root / relative_path).read_bytes() == (
            packaged_root / relative_path
        ).read_bytes()
