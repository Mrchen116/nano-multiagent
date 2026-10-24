"""Protect repeatable daily fixtures and explicit model/approval selection."""

from pathlib import Path

import pytest
import httpx
import yaml

from scripts.e2e_daily import prepare, seed


ROOT = Path(__file__).resolve().parents[2]


def _config(tmp_path: Path, node_id: str) -> Path:
    config = yaml.safe_load((ROOT / "config/e2e/gateway.yaml").read_text())
    config["node"]["node_id"] = node_id
    config["node"]["workspace_base"] = str(tmp_path / ".gateway-workspace")
    config["gateway"] = {
        "environment": {"NANO_OWNER_CONFIG_ROOT": str(tmp_path / ".gateway-owner")}
    }
    path = tmp_path / ".gateway-config.yaml"
    path.write_text(yaml.safe_dump(config))
    return path


def test_new_run_does_not_inherit_project_edits_or_owner_skills(tmp_path: Path) -> None:
    """A down/up in the same directory must start with clean writable assets."""
    path = _config(tmp_path, "run-first")
    prepare(path)
    old = yaml.safe_load(path.read_text())
    old_workspace = Path(old["node"]["workspace_base"])
    (old_workspace / "project/brief.md").write_text("previous-run-edit")
    old_owner = Path(old["gateway"]["environment"]["NANO_OWNER_CONFIG_ROOT"])
    old_skill = old_owner / "skills/previous-run/SKILL.md"
    old_skill.parent.mkdir(parents=True)
    old_skill.write_text("old skill")

    path = _config(tmp_path, "run-second")
    prepare(path)
    new = yaml.safe_load(path.read_text())
    new_workspace = Path(new["node"]["workspace_base"])
    new_owner = Path(new["gateway"]["environment"]["NANO_OWNER_CONFIG_ROOT"])
    assert new_workspace != old_workspace
    assert new_owner != old_owner
    assert "previous-run-edit" not in (new_workspace / "project/brief.md").read_text()
    assert not (new_owner / "skills/previous-run/SKILL.md").exists()
    assert old_skill.read_text() == "old skill"
    policy = yaml.safe_load((new_owner / "config.yaml").read_text())["auto_mode"]
    assert policy["rules"] == "codex" and policy["enabled"] is True
    assert policy["dangerously_skip_permissions"] is False


@pytest.mark.parametrize(
    "model", ["deepseek:deepseek-v4-flash", "kimiCoding:kimi-for-coding"]
)
def test_model_override_preserves_reviewer_and_uses_supported_effort(
    tmp_path: Path, model: str
) -> None:
    """A fixed/high-only model must not inherit Sol's incompatible effort."""
    path = _config(tmp_path, "override-run")
    prepare(path, model_override=model)
    config = yaml.safe_load(path.read_text())
    assert config["llm"]["default_model"] == model
    assert config["llm"]["tool_approval_model"] == "codexOAuth:gpt-6-luna"
    expected_effort = "high" if model.startswith("deepseek:") else None
    for agent in config["agents"]:
        assert agent["default_model"] == model
        assert agent.get("reasoning_effort") == expected_effort
        assert agent["approval_mode"] == "codex"


def test_unknown_model_cannot_silently_change_the_fixture(tmp_path: Path) -> None:
    """A misspelled override fails before writing the generated config."""
    path = _config(tmp_path, "invalid-run")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="not registered"):
        prepare(path, model_override="missing:model")
    assert path.read_bytes() == before


def test_pa_failure_does_not_publish_a_ready_manifest(tmp_path: Path) -> None:
    """An online team is insufficient when the real PA creation fails."""
    path = _config(tmp_path, "pa-failure")
    prepare(path)
    agents = yaml.safe_load(path.read_text())["agents"]

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/im/v1/agents":
            return httpx.Response(200, json=agents)
        assert request.method == "POST" and request.url.path == "/im/v1/personal-agent"
        return httpx.Response(503, json={"detail": "node_capabilities_unavailable"})

    with httpx.Client(
        base_url="http://127.0.0.1:12345", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(
            RuntimeError, match="HTTP 503.*node_capabilities_unavailable"
        ):
            seed(client, path, {"id": "test-owner"})
    assert not (tmp_path / ".e2e-daily.json").exists()
