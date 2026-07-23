"""补齐隔离 critical-path 栈所需的模型目录。"""

from __future__ import annotations

import sys
from collections.abc import MutableMapping
from pathlib import Path

import yaml


E2E_DYNAMIC_AGENT_MODEL = "kimiCoding:kimi-for-coding"


def ensure_model_registered(
    config: MutableMapping[str, object], *, model: str = E2E_DYNAMIC_AGENT_MODEL
) -> None:
    """确保隔离 Gateway 配置能解析 critical-path 动态 Agent 的模型。

    Args:
        config: 从用户主配置复制出的 worktree-local Gateway 配置。
        model: dynamic Agent critical-path 明确指定的模型名称。

    Raises:
        ValueError: 配置没有可承载 Anthropic-compatible 模型的 provider catalog。
    """
    llm = config.get("llm")
    if not isinstance(llm, MutableMapping):
        raise ValueError("config is missing llm mapping")
    providers = llm.get("providers")
    if not isinstance(providers, list):
        raise ValueError("config is missing llm.providers list")
    provider = next(
        (
            item
            for item in providers
            if isinstance(item, MutableMapping) and item.get("name") == "anthropic"
        ),
        None,
    )
    if provider is None:
        raise ValueError("config is missing anthropic provider for critical-path model")
    models = provider.get("models")
    if not isinstance(models, list):
        raise ValueError("anthropic provider is missing models list")
    if any(
        isinstance(item, MutableMapping) and item.get("name") == model
        for item in models
    ):
        return
    models.append({"name": model})


def main() -> int:
    """Update one copied Gateway configuration in place."""
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <gateway-config-path>")
    config_path = Path(sys.argv[1])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, MutableMapping):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    ensure_model_registered(config)
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
