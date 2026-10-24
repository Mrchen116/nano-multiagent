"""Prepare and seed the repository's isolated daily acceptance template."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
from pathlib import Path

import httpx
import yaml

from scripts.e2e_catalog import select_e2e_model


TEMPLATE = Path(__file__).resolve().parents[1] / "config/e2e/daily"


def _team() -> dict:
    return yaml.safe_load((TEMPLATE / "team.yaml").read_text(encoding="utf-8"))


def _default_effort(config: dict, model: str) -> str | None:
    selected = next(
        item
        for provider in config["llm"]["providers"]
        for item in provider["models"]
        if item["name"] == model
    )
    reasoning = selected.get("reasoning")
    return reasoning.get("default") if isinstance(reasoning, dict) else None


def prepare(config_path: Path, *, model_override: str | None = None) -> None:
    """Write a daily config and fresh writable assets inside this runtime root.

    Args:
        config_path: e2e-up's copied, already isolated Gateway configuration.
        model_override: Optional registered route for all working Agents.

    Raises:
        ValueError: An explicit working model is absent from the model catalog.

    Side Effects:
        Writes the copied config, run-specific owner policy and project files.
        Previous runs are retained as evidence but are not read or modified.
    """
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    team = _team()
    base = next(
        agent for agent in config["agents"] if agent["agent_id"] == "e2e-global"
    )
    root = config_path.parent
    node_id = config["node"]["node_id"]
    workspace = root / ".gateway-workspace" / node_id
    owner = root / ".gateway-owner" / node_id
    project = workspace / "project"
    config["node"]["workspace_base"] = str(workspace)
    config["gateway"]["environment"]["NANO_OWNER_CONFIG_ROOT"] = str(owner)
    config["llm"]["default_model"] = team["personal"]["model"]
    config["llm"]["tool_approval_model"] = team["approval_model"]
    config["agents"] = []
    for role in team["agents"]:
        agent = {**copy.deepcopy(base), **role}
        agent.update(
            workspace_root=str(workspace / role["agent_id"]),
            approval_mode="codex",
            model_fallbacks=[],
            custom_prompt=team["shared_prompt"].format(project=project)
            + role["custom_prompt"],
        )
        agent["features"]["heartbeat"] = False
        config["agents"].append(agent)
    if model_override:
        select_e2e_model(config, model=model_override)
        for agent in config["agents"]:
            agent["reasoning_effort"] = _default_effort(config, model_override)

    # Both roots change with the run, including global Skills written by Agents.
    owner.mkdir(parents=True)
    (owner / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "auto_mode": {
                    "enabled": True,
                    "rules": "codex",
                    "dangerously_skip_permissions": False,
                }
            }
        ),
        encoding="utf-8",
    )
    shutil.copytree(TEMPLATE / "project", project)
    for agent in config["agents"]:
        Path(agent["workspace_root"]).mkdir()
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _request(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.is_error:
        raise RuntimeError(
            f"Daily seed {method} {path}: HTTP {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def seed(client: httpx.Client, config_path: Path, user: dict) -> dict:
    """Create a real PA and daily group through the authenticated product API.

    Args:
        client: e2e-up readiness's logged-in test-owner client.
        config_path: Prepared daily Gateway configuration.
        user: Authenticated test owner from the existing login response.

    Returns:
        Non-secret handoff manifest, also saved as .e2e-daily.json.

    Raises:
        RuntimeError: Registration, PA creation or source visibility fails.

    Side Effects:
        Creates PA/group and configures the PA through public APIs. Sends no
        messages and dispatches no work; does not write the running Node config.
    """
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    team = _team()
    expected = {agent["agent_id"] for agent in config["agents"]}
    deadline = time.monotonic() + 30
    while True:
        listed = _request(client, "GET", "/im/v1/agents")
        if expected <= {agent["agent_id"] for agent in listed}:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Daily team did not register within 30s")
        time.sleep(0.5)

    state = _request(
        client,
        "POST",
        "/im/v1/personal-agent",
        json={
            "request_key": "daily-template-v1",
            "display_name": team["personal"]["title"],
            "node_id": config["node"]["node_id"],
        },
    )
    binding = state["binding"]
    pa_path = f"/im/v1/agents/{binding['agent_id']}/config"
    personal = _request(client, "GET", pa_path)
    model = config["llm"]["default_model"]
    personal.update(
        default_model=model,
        reasoning_effort=(
            team["personal"]["reasoning_effort"]
            if model == team["personal"]["model"]
            else _default_effort(config, model)
        ),
        approval_mode="codex",
        model_fallbacks=[],
    )
    personal["features"]["heartbeat"] = False
    _request(client, "PATCH", pa_path, json=personal)

    group = _request(
        client,
        "POST",
        "/im/v1/conversations",
        json={
            "title": team["group_title"],
            "type": "group",
            "visibility": "private",
            "participants": [{"type": "user", "id": user["id"]}]
            + [
                {"type": "agent", "id": agent["agent_id"]} for agent in config["agents"]
            ],
        },
    )
    state = _request(client, "GET", "/im/v1/personal-agent")
    sources = _request(client, "GET", "/im/v1/personal-agent/sources")
    if state["binding"]["status"] != "active" or not any(
        source["id"] == group["id"] and not source["excluded"]
        for source in sources["items"]
    ):
        raise RuntimeError("Daily PA is not active or cannot observe the daily group")

    rows = []
    for agent_id in [agent["agent_id"] for agent in config["agents"]] + [
        binding["agent_id"]
    ]:
        current = _request(client, "GET", f"/im/v1/agents/{agent_id}/config")
        rows.append(
            {
                key: current.get(key)
                for key in (
                    "agent_id",
                    "display_name",
                    "default_model",
                    "reasoning_effort",
                    "approval_mode",
                    "work_mode",
                )
            }
        )
    url = str(client.base_url).rstrip("/")
    manifest = {
        "template_version": team["version"],
        "im_url": url,
        "node_id": config["node"]["node_id"],
        "agents": rows,
        "approval_model": config["llm"]["tool_approval_model"],
        "approval_rules": "codex",
        "approval_effort": "low when supported; selected by runtime",
        "group": {
            "id": group["id"],
            "title": group["title"],
            "url": f"{url}/chat/{group['id']}",
        },
        "personal": {
            "agent_id": binding["agent_id"],
            "conversation_id": binding["conversation_id"],
            "url": f"{url}/chat/{binding['conversation_id']}",
        },
        "project": str(Path(config["node"]["workspace_base"]) / "project"),
    }
    path = config_path.parent / ".e2e-daily.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"daily template ready: {path}")
    print(f"  team: {manifest['group']['url']}")
    print(f"  PA:   {manifest['personal']['url']}")
    return manifest


def main() -> None:
    """Prepare the copied config; seed runs inside e2e-up's readiness session."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    prepare(args.config, model_override=os.getenv("NANO_MULTIAGENT_E2E_MODEL"))


if __name__ == "__main__":
    main()
