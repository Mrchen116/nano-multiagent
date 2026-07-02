from __future__ import annotations

from pathlib import Path
import tomllib

from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
from personal_assistant.config.local_store import load_local_config
from personal_assistant.main import build_runtime
from personal_assistant.product import build_pa_kernel, prompt_for
from personal_assistant.reporter.upstream_reporter import (
    build_agent_capabilities_payload,
    build_runtime_capabilities,
)
from agent.sdk import LLMConfig


def test_install_builtin_skills_copies_missing_feishu_doc(tmp_path: Path) -> None:
    target_root = tmp_path / "home" / ".nanoassistant" / "skills"

    installed = install_builtin_skills(target_root=target_root)

    target = target_root / "feishu-doc" / "SKILL.md"
    assert target.is_file()
    assert "feishu-cli" in target.read_text(encoding="utf-8")
    assert installed["feishu-doc"] == target


def test_install_builtin_skills_does_not_overwrite_existing_user_skill(
    tmp_path: Path,
) -> None:
    target = tmp_path / "home" / ".nanoassistant" / "skills" / "feishu-doc"
    target.mkdir(parents=True)
    skill_file = target / "SKILL.md"
    skill_file.write_text("user customized skill\n", encoding="utf-8")

    installed = install_builtin_skills(target_root=target.parent)

    assert skill_file.read_text(encoding="utf-8") == "user customized skill\n"
    assert installed == {}


def test_builtin_skills_are_included_as_package_data() -> None:
    pyproject_path = Path(__file__).parents[3] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_data = payload["tool"]["setuptools"]["package-data"]

    assert "personal_assistant" in package_data
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


def test_gateway_startup_persists_feishu_doc_for_feishu_bound_allowlist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    feishu_workspace = tmp_path / "agents" / "feishu-agent"
    plain_workspace = tmp_path / "agents" / "plain-agent"
    feishu_workspace.mkdir(parents=True)
    plain_workspace.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: feishu-agent",
                f"    workspace_root: {feishu_workspace}",
                "    skills:",
                "      - existing-skill",
                "  - agent_id: plain-agent",
                f"    workspace_root: {plain_workspace}",
                "    skills:",
                "      - existing-skill",
                "channels:",
                "  - name: feishu:feishu-agent",
                "    settings:",
                "      appId: cli_test",
                "      appSecret: secret_test",
            ]
        )
        + "\n"
        + _LLM_YAML,
        encoding="utf-8",
    )

    build_runtime(load_local_config(config_path))

    saved = load_local_config(config_path)
    by_id = {agent.agent_id: agent for agent in saved.agents}
    assert by_id["feishu-agent"].skills == ("existing-skill", "feishu-doc")
    assert by_id["plain-agent"].skills == ("existing-skill",)


def test_installed_feishu_doc_is_same_source_for_capabilities_preview_and_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    target_root = home / ".nanoassistant" / "skills"
    install_builtin_skills(target_root=target_root)
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
        node_capability_names = {
            item["name"] for item in build_runtime_capabilities(kernel).skills
        }
        agent_capability_names = {
            item["name"]
            for item in build_agent_capabilities_payload(
                kernel, workspace_root=str(workspace)
            )["skills"]
        }
        list_skill_names = {
            skill.name for skill in kernel.list_skills(workspace_root=workspace)
        }
        runtime_skill_names = {
            skill.name
            for skill in kernel._c.runtime.resolve_available_skills(  # type: ignore[attr-defined]
                workspace, include_names=["feishu-doc"]
            )
        }
        preview = kernel.assemble_prompt_preview(
            workspace_root=workspace,
            skill_ids=["feishu-doc"],
            prompt=prompt_for(config.agents[0]),
            enabled_tools=["read"],
        )

        assert "feishu-doc" in node_capability_names
        assert "feishu-doc" in agent_capability_names
        assert "feishu-doc" in list_skill_names
        assert runtime_skill_names == {"feishu-doc"}
        assert "<name>feishu-doc</name>" in preview["prompt"]
        assert str(target_root / "feishu-doc" / "SKILL.md") in preview["prompt"]
    finally:
        kernel.close()
