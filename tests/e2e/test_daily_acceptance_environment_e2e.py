"""Verify the daily profile through real IM and Node processes without LLM calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from .critical_paths._im_client import IMClient


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.e2e
def test_daily_template_creates_real_pa_and_resets_same_root(tmp_path: Path) -> None:
    """A restarted or separate instance keeps the roster but loses prior data."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"}
    env.pop("NANO_MULTIAGENT_E2E_MODEL", None)
    previous_workspace: Path | None = None
    previous_owner: Path | None = None
    for root in [first, first, second]:
        try:
            up = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts/e2e-up.sh"),
                    "--profile",
                    "daily",
                    "--wt",
                    str(root),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert up.returncode == 0, up.stdout + up.stderr
            handoff = json.loads((root / ".e2e-daily.json").read_text())
            config = yaml.safe_load((root / ".gateway-config.yaml").read_text())
            owner = Path(config["gateway"]["environment"]["NANO_OWNER_CONFIG_ROOT"])
            workspace = Path(config["node"]["workspace_base"])
            assert workspace != previous_workspace and owner != previous_owner
            assert (
                "previous-run-edit"
                not in Path(handoff["project"], "brief.md").read_text()
            )
            assert not (owner / "skills/previous-run/SKILL.md").exists()
            assert handoff["approval_model"] == "codexOAuth:gpt-6-luna"
            assert handoff["approval_rules"] == "codex"
            assert len(handoff["agents"]) == 4
            for agent in handoff["agents"]:
                assert agent["approval_mode"] == "codex"
                assert agent["work_mode"] == "global"
                expected = (
                    ("codexOAuth:gpt-6-astra", "medium")
                    if agent["agent_id"] == handoff["personal"]["agent_id"]
                    else ("codexOAuth:gpt-6.1-sol", "high")
                )
                assert (agent["default_model"], agent["reasoning_effort"]) == expected
            client = IMClient(handoff["im_url"])
            try:
                client.register_or_login("nano", "nano1234")
                headers = {"Authorization": f"Bearer {client.token}"}
                pa = client._http.get("/im/v1/personal-agent", headers=headers).json()
                assert pa["binding"]["status"] == "active"
                assert pa["binding"]["owner_user_id"] == client.user_id
                assert (
                    pa["binding"]["conversation_id"]
                    == handoff["personal"]["conversation_id"]
                )
                group = client._http.get(
                    f"/im/v1/conversations/{handoff['group']['id']}", headers=headers
                ).json()
                assert group["title"] == "研发日常" and group["visibility"] == "private"
                members = group["participants"]
                assert len(members) == 4
                assert {
                    member["id"] for member in members if member["type"] == "agent"
                } == {
                    "daily-product",
                    "daily-engineering",
                    "daily-quality",
                }
                sources = client._http.get(
                    "/im/v1/personal-agent/sources", headers=headers
                ).json()
                assert any(
                    item["id"] == handoff["group"]["id"] and not item["excluded"]
                    for item in sources["items"]
                )
                assert client.list_messages(handoff["group"]["id"]) == []
                assert (
                    client.list_messages(handoff["personal"]["conversation_id"]) == []
                )
                conversations = client._http.get(
                    "/im/v1/conversations", headers=headers
                ).json()
                assert not any(
                    item["title"] == "previous-run-group"
                    for item in conversations["items"]
                )
                client.create_group_conversation([], title="previous-run-group")
            finally:
                client.close()
            Path(handoff["project"], "brief.md").write_text("previous-run-edit")
            skill = owner / "skills/previous-run/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: previous-run\ndescription: previous run\n---\nold skill\n"
            )
            previous_workspace, previous_owner = workspace, owner
        finally:
            down = subprocess.run(
                ["bash", str(ROOT / "scripts/e2e-down.sh"), "--wt", str(root)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert down.returncode == 0, down.stdout + down.stderr
        assert not (root / ".im.pid").exists()
        assert not (root / ".gateway.pid").exists()
