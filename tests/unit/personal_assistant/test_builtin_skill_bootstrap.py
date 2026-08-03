from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from agent.sdk import LLMConfig
from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
from personal_assistant.config.local_store import load_local_config
from personal_assistant.product import build_pa_kernel, prompt_for
from personal_assistant.reporter.upstream_reporter import (
    build_agent_capabilities_payload,
    build_runtime_capabilities,
)


@pytest.mark.parametrize("skill_name", ["feishu-doc", "conversation-skill-distiller"])
def test_install_builtin_skills_copies_missing_skill(
    tmp_path: Path,
    skill_name: str,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    target = target_root / skill_name / "SKILL.md"
    assert target.is_file()
    assert installed[skill_name] == target


@pytest.mark.parametrize("skill_name", ["feishu-doc", "conversation-skill-distiller"])
def test_install_builtin_skills_does_not_overwrite_user_skill(
    tmp_path: Path,
    skill_name: str,
) -> None:
    target_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = target_root / skill_name / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("user-owned skill\n", encoding="utf-8")

    installed = install_builtin_skills(target_root=target_root)

    assert skill_name not in installed
    assert skill_file.read_text(encoding="utf-8") == "user-owned skill\n"


def test_builtin_skills_are_included_as_package_data() -> None:
    pyproject_path = Path(__file__).parents[3] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_data = payload["tool"]["setuptools"]["package-data"]

    assert "builtin_skills/**" in package_data["personal_assistant"]


_LLM_YAML = """\
llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
"""


def test_installed_feishu_doc_is_visible_to_capabilities_and_prompt_preview(
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
        node_names = {item["name"] for item in build_runtime_capabilities(kernel).skills}
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
            skill_ids=["feishu-doc"],
            prompt=prompt_for(config.agents[0]),
            enabled_tools=["read"],
        )

        assert "feishu-doc" in node_names
        assert "feishu-doc" in agent_names
        assert "feishu-doc" in discovered_names
        assert "<name>feishu-doc</name>" in preview["prompt"]
    finally:
        kernel.close()
