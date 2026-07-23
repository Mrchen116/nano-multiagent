"""隔离 critical-path Gateway 配置的模型目录回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.e2e_catalog import E2E_DYNAMIC_AGENT_MODEL, ensure_model_registered


def test_ensure_model_registered_adds_critical_path_model_to_catalog() -> None:
    """用户最小 catalog 复制到隔离栈后可解析动态 Agent 模型。"""
    config: dict[str, object] = {
        "llm": {
            "providers": [
                {
                    "name": "anthropic",
                    "base_url": "http://127.0.0.1:4000",
                    "models": [{"name": "kimiCoding:K2.6"}],
                }
            ]
        }
    }

    ensure_model_registered(config)

    models = config["llm"]["providers"][0]["models"]  # type: ignore[index]
    assert models == [
        {"name": "kimiCoding:K2.6"},
        {"name": E2E_DYNAMIC_AGENT_MODEL},
    ]


def test_ensure_model_registered_does_not_duplicate_existing_model() -> None:
    """已包含的模型保持单个 catalog 条目。"""
    config: dict[str, object] = {
        "llm": {
            "providers": [
                {
                    "name": "anthropic",
                    "models": [{"name": E2E_DYNAMIC_AGENT_MODEL}],
                }
            ]
        }
    }

    ensure_model_registered(config)

    models = config["llm"]["providers"][0]["models"]  # type: ignore[index]
    assert models == [{"name": E2E_DYNAMIC_AGENT_MODEL}]


def test_critical_path_wrapper_opts_in_to_catalog_injection() -> None:
    """通用 e2e-up 只在 critical-path wrapper 明确选择时补 Kimi catalog。"""
    repo_root = Path(__file__).resolve().parents[2]
    up_script = (repo_root / "scripts" / "e2e-up.sh").read_text(encoding="utf-8")
    critical_script = (repo_root / "scripts" / "e2e-critical.sh").read_text(
        encoding="utf-8"
    )

    assert 'NANO_MULTIAGENT_ENABLE_CRITICAL_PATH_CATALOG:-}" == "1"' in up_script
    assert 'python3 "$SCRIPT_DIR/e2e_catalog.py" "$WT_CFG"' in up_script
    assert "export NANO_MULTIAGENT_ENABLE_CRITICAL_PATH_CATALOG=1" in critical_script


def test_ensure_model_registered_rejects_missing_anthropic_catalog() -> None:
    """隔离配置缺少目标 provider 时明确拒绝起栈。"""
    config: dict[str, object] = {"llm": {"providers": []}}

    with pytest.raises(ValueError, match="missing anthropic provider"):
        ensure_model_registered(config)
