"""Tests for _parse_llm and LocalConfig.llm field in local_store.py."""

from pathlib import Path

import pytest


_LLM_YAML = """
llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
          extra_request_body:
            thinking:
              type: adaptive
        - name: volcanoArk:doubao-seed-2-0-code-preview-260215
          extra_request_body:
            thinking:
              type: adaptive
    - name: openai_compat
      base_url: http://127.0.0.1:4000
      models:
        - name: codex_oauth:gpt-5.5
"""

_MINIMAL_NODE_YAML = """node:
  node_id: n1
agents:
  - agent_id: a1
"""


def _make_config(tmp_path: Path, extra_yaml: str = "") -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        _MINIMAL_NODE_YAML + f"    workspace_root: {ws}\n" + extra_yaml,
        encoding="utf-8",
    )
    return cfg


def test_load_local_config_parses_llm_payload(tmp_path: Path) -> None:
    from personal_assistant.config.local_store import load_local_config

    cfg = _make_config(tmp_path, _LLM_YAML)
    config = load_local_config(cfg)

    assert config.llm.default_model == "kimiCoding:K2.6"
    assert len(config.llm.providers) == 2
    anthropic = next(p for p in config.llm.providers if p.name == "anthropic")
    assert anthropic.base_url == "http://127.0.0.1:4000"
    k26 = next(m for m in anthropic.models if m.name == "kimiCoding:K2.6")
    assert k26.extra_request_body == {"thinking": {"type": "adaptive"}}


def test_load_local_config_missing_llm_raises(tmp_path: Path) -> None:
    from personal_assistant.config.local_store import load_local_config

    cfg = _make_config(tmp_path, "")  # no llm section
    with pytest.raises(ValueError, match="llm"):
        load_local_config(cfg)


def test_load_local_config_agent_default_model_validated_against_llm(
    tmp_path: Path,
) -> None:
    """agent.default_model must exist in llm.providers.*.models; else hard fail."""
    from personal_assistant.config.local_store import load_local_config

    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        _MINIMAL_NODE_YAML
        + f"    workspace_root: {ws}\n"
        + "    default_model: nonexistent:model\n"
        + _LLM_YAML,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nonexistent:model"):
        load_local_config(cfg)


def test_load_local_config_agent_no_default_model_ok(tmp_path: Path) -> None:
    """agent without default_model must load fine (falls back to llm.default_model at runtime)."""
    from personal_assistant.config.local_store import load_local_config

    cfg = _make_config(tmp_path, _LLM_YAML)
    config = load_local_config(cfg)
    assert config.agents[0].default_model is None


def test_save_and_reload_preserves_llm(tmp_path: Path) -> None:
    """save_local_config must roundtrip the llm segment."""
    from personal_assistant.config.local_store import (
        load_local_config,
        save_local_config,
    )

    cfg = _make_config(tmp_path, _LLM_YAML)
    original = load_local_config(cfg)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)

    restored = load_local_config(saved_path)
    assert restored.llm.default_model == original.llm.default_model
    assert len(restored.llm.providers) == len(original.llm.providers)
    orig_anthropic = next(p for p in original.llm.providers if p.name == "anthropic")
    rest_anthropic = next(p for p in restored.llm.providers if p.name == "anthropic")
    assert rest_anthropic.base_url == orig_anthropic.base_url
    orig_k26 = next(m for m in orig_anthropic.models if m.name == "kimiCoding:K2.6")
    rest_k26 = next(m for m in rest_anthropic.models if m.name == "kimiCoding:K2.6")
    assert rest_k26.extra_request_body == orig_k26.extra_request_body
