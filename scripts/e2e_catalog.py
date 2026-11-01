"""选择隔离 critical-path 栈要使用的已登记模型。"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import MutableMapping
from pathlib import Path

import yaml
import httpx


E2E_MODEL_ENV = "NANO_MULTIAGENT_E2E_MODEL"


def sync_default_tools(
    client: httpx.Client, config_path: Path, *, explicit_config: bool = False
) -> None:
    """Apply current product defaults to registered default/daily test agents.

    Args:
        client: Authenticated owner client for this isolated stack.
        config_path: Stack configuration identifying its seeded agents.
        explicit_config: Preserve a caller's intentional capability restrictions.
    """
    if explicit_config:
        return
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    expected = {agent["agent_id"] for agent in config["agents"]}

    def request(method: str, path: str, **kwargs):
        response = client.request(method, path, **kwargs)
        if response.is_error:
            raise RuntimeError(
                f"Test capability sync {method} {path}: HTTP {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    deadline = time.monotonic() + 30
    while not expected <= {
        agent["agent_id"] for agent in request("GET", "/im/v1/agents")
    }:
        if time.monotonic() >= deadline:
            raise RuntimeError("Test agents did not register within 30s")
        time.sleep(0.5)
    for agent_id in sorted(expected):
        path = f"/im/v1/agents/{agent_id}"
        catalog = request("GET", path + "/capabilities")
        current = request("GET", path + "/config")
        available = {tool["name"] for tool in catalog["tools"]}
        selected = set(current.get("tool_allowlist") or []) & available
        selected.update(tool["name"] for tool in catalog["tools"] if tool["default_on"])
        selected.update(catalog["fixed_tools"])
        for feature in catalog["features"]:
            if current["features"].get(feature["key"]):
                selected.update(feature["requires"]["tools"])
        if selected != set(current.get("tool_allowlist") or []):
            request(
                "PATCH",
                path + "/config",
                json={**current, "tool_allowlist": sorted(selected)},
            )


def select_e2e_model(
    config: MutableMapping[str, object], *, model: str | None = None
) -> str:
    """Select a registered model for every real-LLM critical-path agent.

    Args:
        config: 从用户主配置复制出的 worktree-local Gateway 配置。
        model: Explicit route from ``NANO_MULTIAGENT_E2E_MODEL``. ``None`` keeps
            the copied configuration's default model.

    Raises:
        ValueError: 配置缺少默认模型，或所选模型不在配置 catalog 中。

    Returns:
        The selected model route.
    """
    llm = config.get("llm")
    if not isinstance(llm, MutableMapping):
        raise ValueError("config is missing llm mapping")
    configured_default = llm.get("default_model")
    selected = model or configured_default
    if not isinstance(selected, str) or not selected:
        raise ValueError("config is missing llm.default_model")
    providers = llm.get("providers")
    if not isinstance(providers, list):
        raise ValueError("config is missing llm.providers list")
    if not any(
        isinstance(provider, MutableMapping)
        and isinstance(provider.get("models"), list)
        and any(
            isinstance(candidate, MutableMapping) and candidate.get("name") == selected
            for candidate in provider["models"]
        )
        for provider in providers
    ):
        raise ValueError(
            f"selected E2E model {selected!r} is not registered in llm.providers"
        )
    llm["default_model"] = selected
    agents = config.get("agents")
    if isinstance(agents, list):
        for agent in agents:
            if isinstance(agent, MutableMapping):
                agent["default_model"] = selected
    return selected


def main() -> int:
    """Update one copied Gateway configuration in place."""
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <gateway-config-path>")
    config_path = Path(sys.argv[1])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, MutableMapping):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    select_e2e_model(config, model=os.getenv(E2E_MODEL_ENV))
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
