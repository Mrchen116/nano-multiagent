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
          reasoning:
            default: high
            levels: [low, high]
          extra_request_body:
            thinking:
              type: adaptive
        - name: volcanoArk:doubao-seed-2-0-code-preview-260215
          reasoning: fixed
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
    assert k26.reasoning is not None
    assert k26.reasoning.default == "high"
    assert k26.reasoning.levels == ("low", "high")
    fixed = next(
        m
        for m in anthropic.models
        if m.name == "volcanoArk:doubao-seed-2-0-code-preview-260215"
    )
    assert fixed.reasoning is not None
    assert fixed.reasoning.kind == "fixed"
    assert config.llm.tool_approval_model is None


def test_load_local_config_parses_tool_approval_model(tmp_path: Path) -> None:
    from personal_assistant.config.local_store import load_local_config

    llm_yaml = _LLM_YAML.replace(
        "  default_model: kimiCoding:K2.6\n",
        "  default_model: kimiCoding:K2.6\n"
        "  tool_approval_model: codex_oauth:gpt-5.5\n",
    )
    config = load_local_config(_make_config(tmp_path, llm_yaml))

    assert config.llm.tool_approval_model == "codex_oauth:gpt-5.5"


@pytest.mark.parametrize("value", ["'   '", "missing:model"])
def test_load_local_config_rejects_invalid_tool_approval_model(
    tmp_path: Path, value: str
) -> None:
    from personal_assistant.config.local_store import load_local_config

    llm_yaml = _LLM_YAML.replace(
        "  default_model: kimiCoding:K2.6\n",
        f"  default_model: kimiCoding:K2.6\n  tool_approval_model: {value}\n",
    )

    with pytest.raises(ValueError, match="llm.tool_approval_model"):
        load_local_config(_make_config(tmp_path, llm_yaml))


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


def test_load_local_config_rejects_duplicate_model_names_across_providers(
    tmp_path: Path,
) -> None:
    """One model id cannot name different provider routes and capabilities."""
    from personal_assistant.config.local_store import load_local_config

    duplicate_model_yaml = _LLM_YAML.replace(
        "        - name: codex_oauth:gpt-5.5\n",
        "        - name: kimiCoding:K2.6\n",
    )

    with pytest.raises(ValueError, match="must not repeat a model name"):
        load_local_config(_make_config(tmp_path, duplicate_model_yaml))


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

    llm_yaml = _LLM_YAML.replace(
        "  default_model: kimiCoding:K2.6\n",
        "  default_model: kimiCoding:K2.6\n"
        "  tool_approval_model: codex_oauth:gpt-5.5\n",
    )
    cfg = _make_config(tmp_path, llm_yaml)
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
    assert rest_k26.reasoning == orig_k26.reasoning
    assert restored.llm.tool_approval_model == "codex_oauth:gpt-5.5"


@pytest.mark.parametrize(
    "reasoning_yaml",
    [
        "reasoning: variable",
        "reasoning: {default: high, levels: []}",
        "reasoning: {default: high, levels: [low]}",
        "reasoning: {default: high, levels: [high, high]}",
    ],
)
def test_load_local_config_rejects_invalid_reasoning_schema(
    tmp_path: Path, reasoning_yaml: str
) -> None:
    from personal_assistant.config.local_store import load_local_config

    llm_yaml = _LLM_YAML.replace(
        "          reasoning:\n"
        "            default: high\n"
        "            levels: [low, high]\n",
        f"          {reasoning_yaml}\n",
    )

    with pytest.raises(ValueError, match="reasoning"):
        load_local_config(_make_config(tmp_path, llm_yaml))


def test_stale_agent_reasoning_loads_but_runtime_resolution_rejects(
    tmp_path: Path,
) -> None:
    from personal_assistant.config.local_store import load_local_config
    from personal_assistant.config.model_reasoning import ModelReasoningCatalog

    config_path = _make_config(tmp_path, _LLM_YAML)
    text = config_path.read_text(encoding="utf-8").replace(
        "    workspace_root:",
        "    default_model: kimiCoding:K2.6\n"
        "    reasoning_effort: max\n"
        "    workspace_root:",
    )
    config_path.write_text(text, encoding="utf-8")

    config = load_local_config(config_path)

    with pytest.raises(ValueError, match="reasoning_effort"):
        ModelReasoningCatalog(config.llm).resolve(
            "kimiCoding:K2.6", config.agents[0].reasoning_effort
        )


def test_reasoning_catalog_resolves_default_and_runtime_projection(
    tmp_path: Path,
) -> None:
    from personal_assistant.config.local_store import (
        AgentWorkspaceConfig,
        load_local_config,
    )
    from personal_assistant.config.model_reasoning import ModelReasoningCatalog
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.session_composition import project_agent_runtime

    config = load_local_config(_make_config(tmp_path, _LLM_YAML))
    catalog = ModelReasoningCatalog(config.llm)
    agent = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="a",
                workspace_root=tmp_path / "ws",
                default_model="kimiCoding:K2.6",
            ),
        )
    ).require("a")

    projected = project_agent_runtime(
        agent,
        scenario={},
        resolved_model="kimiCoding:K2.6",
        reasoning_catalog=catalog,
    )

    assert catalog.resolve("kimiCoding:K2.6", None) == "high"
    assert projected.runtime.reasoning_effort == "high"

    inherited_agent = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="inherited",
                workspace_root=tmp_path / "ws",
                reasoning_effort="low",
            ),
        )
    ).require("inherited")
    inherited = project_agent_runtime(
        inherited_agent,
        scenario={},
        resolved_model="kimiCoding:K2.6",
        reasoning_catalog=catalog,
    )

    catalog.validate(None, "low")
    assert inherited.runtime.reasoning_effort == "low"


def test_agent_reasoning_effort_round_trips_local_config(tmp_path: Path) -> None:
    from personal_assistant.config.local_store import (
        load_local_config,
        save_local_config,
    )

    config_path = _make_config(tmp_path, _LLM_YAML)
    text = config_path.read_text(encoding="utf-8").replace(
        "    workspace_root:",
        "    default_model: kimiCoding:K2.6\n"
        "    reasoning_effort: low\n"
        "    workspace_root:",
    )
    config_path.write_text(text, encoding="utf-8")

    loaded = load_local_config(config_path)
    save_local_config(loaded, config_path)
    restored = load_local_config(config_path)

    assert restored.agents[0].default_model == "kimiCoding:K2.6"
    assert restored.agents[0].reasoning_effort == "low"


_LLM_YAML_CONTEXT_WINDOW = """
llm:
  default_model: big:model
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: big:model
          context_window: 1000000
        - name: plain:model
        - name: bad:model
          context_window: 0
"""


def test_load_local_config_parses_context_window(tmp_path: Path) -> None:
    """feat-436: 模型条目的 context_window 被解析；未配 / 非法值（0）→ None，不让加载失败。"""
    from personal_assistant.config.local_store import load_local_config

    cfg = _make_config(tmp_path, _LLM_YAML_CONTEXT_WINDOW)
    config = load_local_config(cfg)

    models = {m.name: m for m in config.llm.providers[0].models}
    assert models["big:model"].context_window == 1000000
    assert models["plain:model"].context_window is None
    assert models["bad:model"].context_window is None  # 0 归一为未配


def test_save_and_reload_preserves_context_window(tmp_path: Path) -> None:
    """save_local_config 回写保留 context_window；未配的模型不落该字段。"""
    from personal_assistant.config.local_store import (
        load_local_config,
        save_local_config,
    )

    cfg = _make_config(tmp_path, _LLM_YAML_CONTEXT_WINDOW)
    original = load_local_config(cfg)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)

    restored = load_local_config(saved_path)
    models = {m.name: m for m in restored.llm.providers[0].models}
    assert models["big:model"].context_window == 1000000
    assert models["plain:model"].context_window is None
