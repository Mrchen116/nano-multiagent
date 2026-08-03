"""选择隔离 critical-path 栈要使用的已登记模型。"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

import yaml


E2E_MODEL_ENV = "NANO_MULTIAGENT_E2E_MODEL"


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
