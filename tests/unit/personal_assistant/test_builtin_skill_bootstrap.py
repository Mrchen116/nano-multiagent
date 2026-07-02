from __future__ import annotations

from pathlib import Path
import tomllib

from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
from personal_assistant.config.local_store import load_local_config
from personal_assistant.main import build_runtime


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
