from pathlib import Path

import pytest

from personal_assistant.config.local_store import DEFAULT_LOCAL_KERNEL_TOKEN, default_local_config_path, load_local_config, save_local_config


# Minimal llm: section required by all Gateway configs after refactor-382.
_LLM_YAML = """\
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
    - name: openai_compat
      base_url: http://127.0.0.1:4000
      models:
        - name: codex_oauth:gpt-5.5
"""


def test_load_local_config_defaults_workspace_root_to_user_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    expected_root = home_dir / "nano-assistant" / "workspace" / "assistant-a"
    assert config.agents[0].workspace_root == expected_root.resolve()
    assert expected_root.is_dir() is True
    # MEMORY.md and USER.md seeded under .nanoassistant/memory/ (feat-349-M3 migration).
    assert (expected_root / ".nanoassistant" / "memory" / "MEMORY.md").is_file() is True
    assert (expected_root / "HEARTBEAT.md").is_file() is True
    assert (expected_root / ".nanoassistant" / "memory" / "MEMORY.md").read_text(encoding="utf-8").strip()
    assert (expected_root / "HEARTBEAT.md").read_text(encoding="utf-8").strip()


def test_load_local_config_backfills_default_workspace_files_for_explicit_root(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.agents[0].workspace_root == workspace_root
    # MEMORY.md seeded under .nanoassistant/memory/ (feat-349-M3 migration).
    assert (workspace_root / ".nanoassistant" / "memory" / "MEMORY.md").is_file() is True
    assert (workspace_root / "HEARTBEAT.md").is_file() is True


def test_load_local_config_does_not_overwrite_existing_workspace_files(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    memory_dir = workspace_root / ".nanoassistant" / "memory"
    memory_dir.mkdir(parents=True)
    memory_path = memory_dir / "MEMORY.md"
    heartbeat_path = workspace_root / "HEARTBEAT.md"
    memory_path.write_text("existing memory\n", encoding="utf-8")
    heartbeat_path.write_text("interval: 1h\n\n- Existing heartbeat\n", encoding="utf-8")
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    load_local_config(config_path)

    assert memory_path.read_text(encoding="utf-8") == "existing memory\n"
    assert heartbeat_path.read_text(encoding="utf-8") == "interval: 1h\n\n- Existing heartbeat\n"


def test_load_local_config_keeps_explicit_workspace_root_requirement(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    explicit_root = tmp_path / "agents" / "assistant-a"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {explicit_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workspace_root does not exist"):
        load_local_config(config_path)


def test_load_local_config_reads_yaml_and_applies_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
                "channels:",
                "  - name: web_relay",
                "kernel:",
                "  base_url: http://127.0.0.1:8100",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.node.node_id == "node-local"
    assert config.kernel.base_url == "http://127.0.0.1:8100"
    assert config.kernel.health_path == "/v1/health"
    assert config.kernel.startup_timeout_seconds == 15.0
    assert config.agents[0].workspace_root == workspace_root
    assert config.channels[0].enabled is True
    assert config.im_service is None


def test_load_local_config_preserves_multiple_seed_agents_in_order(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    alpha_root = tmp_path / "agents" / "alpha"
    beta_root = tmp_path / "agents" / "beta"
    alpha_root.mkdir(parents=True)
    beta_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: Alpha",
                f"    workspace_root: {alpha_root}",
                "    title: Alpha",
                "  - agent_id: Beta",
                f"    workspace_root: {beta_root}",
                "    title: Beta",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert [agent.agent_id for agent in config.agents] == ["Alpha", "Beta"]
    assert [agent.title for agent in config.agents] == ["Alpha", "Beta"]
    assert [agent.workspace_root for agent in config.agents] == [alpha_root, beta_root]


def test_load_local_config_uses_internal_kernel_base_url_default(tmp_path: Path) -> None:
    # refactor-387-M4: kernel is in-process; kernel.command is empty (no subprocess).
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.kernel.base_url == "http://127.0.0.1:8000"
    assert config.kernel.command == ""  # in-process: no subprocess command needed
    assert config.agents[0].workspace_root == workspace_root


def test_load_local_config_defaults_kernel_command_to_real_http_app_entrypoint(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    # refactor-387 M3: kernel_app.py deleted; default command is now empty string
    assert config.kernel.command == ""
    assert config.kernel.base_url == "http://127.0.0.1:8000"
    assert config.agents[0].workspace_root == workspace_root


def test_load_local_config_defaults_kernel_token_for_local_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    monkeypatch.delenv("NANO_MULTIAGENT_API_TOKEN", raising=False)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.kernel.token == DEFAULT_LOCAL_KERNEL_TOKEN


def test_load_local_config_derives_kernel_base_url_from_local_command_port(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
                "kernel:",
                "  command: python -m uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port 8123",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.kernel.base_url == "http://127.0.0.1:8123"
    assert config.kernel.command.endswith("--host 127.0.0.1 --port 8123")
    assert config.agents[0].workspace_root == workspace_root


def test_load_local_config_rejects_missing_agents(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents: []",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="agents must contain at least one entry"):
        load_local_config(config_path)


def test_load_local_config_rejects_missing_workspace_root(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    missing_root = tmp_path / "agents" / "missing"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {missing_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workspace_root does not exist"):
        load_local_config(config_path)


def test_parse_agents_defaults_new_fields_to_none(tmp_path: Path) -> None:
    """YAML without extended fields loads with None/empty defaults."""
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)
    agent = config.agents[0]

    assert agent.system_prompt is None
    assert agent.group_reply_policy is None
    assert agent.default_model is None
    assert agent.skills == ()
    assert agent.tool_allowlist == ()


def test_parse_agents_loads_extended_fields(tmp_path: Path) -> None:
    """YAML with all extended agent fields are parsed into AgentWorkspaceConfig."""
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
                "    title: My Agent",
                "    system_prompt: You are a helpful assistant.",
                "    skills:",
                "      - web_search",
                "      - code_review",
                "    tool_allowlist:",
                "      - Read",
                "      - Write",
                "    group_reply_policy: always",
                "    default_model: codex_oauth:gpt-5.5",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)
    agent = config.agents[0]

    assert agent.system_prompt == "You are a helpful assistant."
    assert agent.skills == ("web_search", "code_review")
    assert agent.tool_allowlist == ("Read", "Write")
    assert agent.group_reply_policy == "always"
    assert agent.default_model == "codex_oauth:gpt-5.5"


def test_save_local_config_round_trip(tmp_path: Path) -> None:
    """Load config, save it, reload — fields must be equivalent."""
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "  user_id: u1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
                "    title: My Agent",
                "    system_prompt: You are helpful.",
                "    skills:",
                "      - web_search",
                "    tool_allowlist:",
                "      - Read",
                "    group_reply_policy: always",
                "    default_model: codex_oauth:gpt-5.5",
                "channels:",
                "  - name: web_relay",
                "    enabled: true",
                "    settings:",
                "      port: 8080",
                "im_service:",
                "  url: wss://im.example.com",
                "  token: secret-token",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    original = load_local_config(config_path)
    saved_path = tmp_path / "saved-config.yaml"
    save_local_config(original, saved_path)
    reloaded = load_local_config(saved_path)

    # Node
    assert reloaded.node.node_id == original.node.node_id
    assert reloaded.node.user_id == original.node.user_id
    # Agent fields round-trip
    assert len(reloaded.agents) == len(original.agents)
    orig_agent = original.agents[0]
    reload_agent = reloaded.agents[0]
    assert reload_agent.agent_id == orig_agent.agent_id
    assert reload_agent.workspace_root == orig_agent.workspace_root
    assert reload_agent.title == orig_agent.title
    assert reload_agent.system_prompt == orig_agent.system_prompt
    assert reload_agent.skills == orig_agent.skills
    assert reload_agent.tool_allowlist == orig_agent.tool_allowlist
    assert reload_agent.group_reply_policy == orig_agent.group_reply_policy
    assert reload_agent.default_model == orig_agent.default_model
    # Channels
    assert len(reloaded.channels) == len(original.channels)
    assert reloaded.channels[0].name == original.channels[0].name
    # IM service
    assert reloaded.im_service is not None
    assert reloaded.im_service.url == original.im_service.url
    assert reloaded.im_service.token == original.im_service.token


def test_save_local_config_creates_missing_parent_directories(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "assistant-a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-local",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    original = load_local_config(config_path)
    saved_path = tmp_path / "missing" / "dir" / "config.yaml"

    save_local_config(original, saved_path)

    assert saved_path.exists() is True


def test_default_local_config_path_uses_user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))

    assert default_local_config_path() == (home_dir / ".nano-assistant" / "config.yaml").resolve()


def test_im_service_config_refresh_token_and_credentials_round_trip(tmp_path: Path) -> None:
    """IMServiceConfig parses refresh_token/username/password and saves them back."""
    config_path = tmp_path / "config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
                "im_service:",
                "  url: http://localhost:8011",
                "  token: access-abc",
                "  refresh_token: refresh-xyz",
                "  username: nano",
                "  password: nano1234",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.im_service is not None
    assert config.im_service.token == "access-abc"
    assert config.im_service.refresh_token == "refresh-xyz"
    assert config.im_service.username == "nano"
    assert config.im_service.password == "nano1234"

    saved_path = tmp_path / "saved.yaml"
    save_local_config(config, saved_path)
    reloaded = load_local_config(saved_path)

    assert reloaded.im_service is not None
    assert reloaded.im_service.refresh_token == "refresh-xyz"
    assert reloaded.im_service.username == "nano"
    assert reloaded.im_service.password == "nano1234"


def test_im_service_config_optional_fields_default_to_none(tmp_path: Path) -> None:
    """refresh_token/username/password are optional and default to None when absent."""
    config_path = tmp_path / "config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
                "im_service:",
                "  url: http://localhost:8011",
                "  token: access-abc",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.im_service is not None
    assert config.im_service.refresh_token is None
    assert config.im_service.username is None
    assert config.im_service.password is None


# ---------------------------------------------------------------------------
# R4 tests: ensure_workspace_defaults seed location migration (feat-349-M3)
# ---------------------------------------------------------------------------


def test_ensure_workspace_defaults_seeds_memory_under_nanoassistant_memory(tmp_path: Path) -> None:
    """MEMORY.md must be seeded at <workspace_root>/.nanoassistant/memory/MEMORY.md (MemoryStore path)."""
    from personal_assistant.config.local_store import ensure_workspace_defaults

    resolved = ensure_workspace_defaults(tmp_path)
    memory_path = resolved / ".nanoassistant" / "memory" / "MEMORY.md"
    assert memory_path.is_file(), f"Expected {memory_path} to exist"


def test_ensure_workspace_defaults_seeds_user_under_nanoassistant_memory(tmp_path: Path) -> None:
    """USER.md must be seeded at <workspace_root>/.nanoassistant/memory/USER.md."""
    from personal_assistant.config.local_store import ensure_workspace_defaults

    resolved = ensure_workspace_defaults(tmp_path)
    user_path = resolved / ".nanoassistant" / "memory" / "USER.md"
    assert user_path.is_file(), f"Expected {user_path} to exist"


def test_ensure_workspace_defaults_seeds_heartbeat_at_workspace_root(tmp_path: Path) -> None:
    """HEARTBEAT.md remains at workspace root (not under .nanoassistant/)."""
    from personal_assistant.config.local_store import ensure_workspace_defaults

    resolved = ensure_workspace_defaults(tmp_path)
    heartbeat_path = resolved / "HEARTBEAT.md"
    assert heartbeat_path.is_file(), f"Expected {heartbeat_path} to exist"


def test_ensure_workspace_defaults_does_not_overwrite_existing_memory(tmp_path: Path) -> None:
    """Existing MEMORY.md in new location is not overwritten."""
    from personal_assistant.config.local_store import ensure_workspace_defaults

    memory_dir = tmp_path / ".nanoassistant" / "memory"
    memory_dir.mkdir(parents=True)
    existing = memory_dir / "MEMORY.md"
    existing.write_text("existing content\n", encoding="utf-8")

    ensure_workspace_defaults(tmp_path)

    assert existing.read_text(encoding="utf-8") == "existing content\n"


def test_save_local_config_omits_none_fields(tmp_path: Path) -> None:
    """Saved YAML should not contain keys for None-valued optional fields."""
    import yaml as _yaml

    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agents" / "a"
    workspace_root.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: n1",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace_root}",
            ]
        ) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )

    original = load_local_config(config_path)
    saved_path = tmp_path / "saved-config.yaml"
    save_local_config(original, saved_path)

    raw = _yaml.safe_load(saved_path.read_text(encoding="utf-8"))
    agent_raw = raw["agents"][0]
    # None fields should be absent from serialized YAML
    assert "system_prompt" not in agent_raw
    assert "group_reply_policy" not in agent_raw
    assert "default_model" not in agent_raw
    assert "title" not in agent_raw
    # Empty tuples should also be absent
    assert "skills" not in agent_raw
    assert "tool_allowlist" not in agent_raw


# ---------------------------------------------------------------------------
# feat-379-M2/R1: features + custom_prompt per-agent fields
# ---------------------------------------------------------------------------

def test_agent_workspace_config_has_features_field(tmp_path: Path) -> None:
    """AgentWorkspaceConfig must expose a features mapping (feat-379 decision 3)."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    # features must exist and default to empty mapping
    assert hasattr(config.agents[0], "features")
    assert dict(config.agents[0].features) == {}


def test_agent_workspace_config_has_custom_prompt_field(tmp_path: Path) -> None:
    """AgentWorkspaceConfig must expose custom_prompt (feat-379 decision 5)."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    assert hasattr(config.agents[0], "custom_prompt")
    assert config.agents[0].custom_prompt is None


def test_load_features_from_yaml(tmp_path: Path) -> None:
    """YAML features dict must be parsed into AgentWorkspaceConfig.features."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
            "    features:",
            "      memory_curation: false",
            "      skill_creation: true",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    assert config.agents[0].features["memory_curation"] is False
    assert config.agents[0].features["skill_creation"] is True


def test_load_custom_prompt_from_yaml(tmp_path: Path) -> None:
    """YAML custom_prompt string must be parsed into AgentWorkspaceConfig.custom_prompt."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
            "    custom_prompt: 你是我的私人法律顾问",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    assert config.agents[0].custom_prompt == "你是我的私人法律顾问"


def test_save_features_round_trip(tmp_path: Path) -> None:
    """features must survive load → save → load round-trip."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
            "    features:",
            "      memory_curation: false",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    original = load_local_config(config_path)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)
    reloaded = load_local_config(saved_path)
    assert reloaded.agents[0].features["memory_curation"] is False


def test_save_custom_prompt_round_trip(tmp_path: Path) -> None:
    """custom_prompt must survive load → save → load round-trip."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
            "    custom_prompt: 你是我的私人法律顾问",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    original = load_local_config(config_path)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)
    reloaded = load_local_config(saved_path)
    assert reloaded.agents[0].custom_prompt == "你是我的私人法律顾问"


def test_save_omits_empty_features(tmp_path: Path) -> None:
    """Empty features dict must not be written to YAML output."""
    import yaml as _yaml

    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    original = load_local_config(config_path)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)
    raw = _yaml.safe_load(saved_path.read_text(encoding="utf-8"))
    assert "features" not in raw["agents"][0]


def test_save_omits_none_custom_prompt(tmp_path: Path) -> None:
    """None custom_prompt must not appear in serialized YAML."""
    import yaml as _yaml

    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n1",
            "agents:",
            f"  - agent_id: alpha",
            f"    workspace_root: {workspace_root}",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    original = load_local_config(config_path)
    saved_path = tmp_path / "saved.yaml"
    save_local_config(original, saved_path)
    raw = _yaml.safe_load(saved_path.read_text(encoding="utf-8"))
    assert "custom_prompt" not in raw["agents"][0]


# ---------------------------------------------------------------------------
# feat-386: save_local_config 写前备份 (backup-on-write)
#
# 所有用例通过 monkeypatch default_local_config_path 把"主配置"路由到 tmp_path，
# 保持单测幂等、无真实 home 副作用。
# ---------------------------------------------------------------------------

def _make_minimal_config(tmp_path: Path) -> "LocalConfig":
    """Return a minimal LocalConfig with workspace and config under a 'src' subdir.

    Uses a dedicated subdirectory so callers can freely control files at
    tmp_path root (e.g. place or omit a main config.yaml) without colliding
    with the bootstrap config written here.
    """
    src_dir = tmp_path / "_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = src_dir / "workspace" / "agent-a"
    workspace_root.mkdir(parents=True)
    config_path = src_dir / "bootstrap.yaml"
    config_path.write_text(
        "\n".join([
            "node:",
            "  node_id: n-test",
            "agents:",
            f"  - agent_id: agent-a",
            f"    workspace_root: {workspace_root}",
        ]) + "\n" + _LLM_YAML,
        encoding="utf-8",
    )
    return load_local_config(config_path)


def test_save_local_config_creates_backup_for_main_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """写盘主配置时备份文件出现在 backups/ 子目录，内容等于写盘前的旧版。"""
    import personal_assistant.config.local_store as ls

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)
    # 先写一个"旧版"作为将被备份的内容
    old_text = "# old version\n"
    main_cfg.write_text(old_text, encoding="utf-8")

    save_local_config(cfg, main_cfg)

    backups_dir = main_cfg.parent / "backups"
    assert backups_dir.is_dir(), "backups/ 子目录应被创建"
    bak_files = sorted(backups_dir.glob("config.*.yaml.bak"))
    assert len(bak_files) == 1, "应产生恰好一份备份"
    assert bak_files[0].read_text(encoding="utf-8") == old_text, "备份内容应等于旧版"


def test_save_local_config_no_backup_when_dest_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """首次写盘（dest 不存在）不产生备份文件。"""
    import personal_assistant.config.local_store as ls

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)
    assert not main_cfg.exists(), "前置条件：dest 不存在"

    save_local_config(cfg, main_cfg)

    backups_dir = main_cfg.parent / "backups"
    bak_files = list(backups_dir.glob("config.*.yaml.bak")) if backups_dir.exists() else []
    assert len(bak_files) == 0, "首次写盘不应产生备份"


def test_save_local_config_no_backup_for_non_main_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """非默认主配置路径（worktree 副本等）不产生备份。"""
    import personal_assistant.config.local_store as ls

    # 主配置指向另一个路径，与 save 目标不同
    other_main = tmp_path / "other" / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: other_main.resolve())

    side_path = tmp_path / "side-config.yaml"
    side_path.write_text("# side\n", encoding="utf-8")

    cfg = _make_minimal_config(tmp_path)
    save_local_config(cfg, side_path)

    backups_dir = side_path.parent / "backups"
    bak_files = list(backups_dir.glob("config.*.yaml.bak")) if backups_dir.exists() else []
    assert len(bak_files) == 0, "非主配置路径不应产生备份"


def test_save_local_config_skips_backup_when_content_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """新序列化内容与 dest 现有内容逐字节相同时跳过备份（no-op churn 防护）。"""
    import personal_assistant.config.local_store as ls

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)
    # 先正常写一次，dest 现在已含正确内容
    save_local_config(cfg, main_cfg)

    # 第二次写相同内容，不应再产生备份
    backups_dir = main_cfg.parent / "backups"
    bak_before = set(backups_dir.glob("config.*.yaml.bak")) if backups_dir.exists() else set()
    save_local_config(cfg, main_cfg)
    bak_after = set(backups_dir.glob("config.*.yaml.bak")) if backups_dir.exists() else set()

    assert bak_after == bak_before, "内容相同时第二次不应产生新备份"


def test_save_local_config_backup_retains_at_most_30_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """backups/ 目录应裁剪至最近 30 份，超出删最旧。"""
    import personal_assistant.config.local_store as ls
    import time as _time

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)

    # 写 35 次，每次先改 dest 内容让序列化结果不同（触发备份）
    for i in range(35):
        main_cfg.write_text(f"# version {i}\n", encoding="utf-8")
        # 避免同一秒内文件名碰撞：借助 monkeypatch 注入人工时间戳不可行时，
        # 小量 sleep 或依靠实现的去碰撞机制——这里测留存裁剪逻辑，
        # 因此直接用 backups/ 数量断言。
        save_local_config(cfg, main_cfg)

    backups_dir = main_cfg.parent / "backups"
    bak_files = sorted(backups_dir.glob("config.*.yaml.bak"))
    assert len(bak_files) <= 30, f"备份应裁剪至至多 30 份，实际 {len(bak_files)} 份"


def test_save_local_config_concurrent_backups_do_not_overwrite_each_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """同一时刻（单调时间戳相同）两次备份不互相覆盖。"""
    import personal_assistant.config.local_store as ls
    from unittest.mock import patch
    from datetime import datetime, timezone

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)

    fixed_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 两次写，都伪造成同一时间戳，期望不产生同名覆盖
    written_texts: list[str] = []
    for i in range(2):
        text = f"# v{i}\n"
        main_cfg.write_text(text, encoding="utf-8")
        written_texts.append(text)
        with patch("personal_assistant.config.local_store.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dt
            mock_dt.side_effect = None
            save_local_config(cfg, main_cfg)

    backups_dir = main_cfg.parent / "backups"
    bak_files = sorted(backups_dir.glob("config.*.yaml.bak"))
    assert len(bak_files) == 2, "同秒两次写盘应产生两份不同名备份"
    bak_contents = {f.read_text(encoding="utf-8") for f in bak_files}
    assert bak_contents == set(written_texts), "两份备份内容应各不相同"


def test_save_local_config_backup_failure_raises_and_leaves_dest_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """备份失败（目录无写权限）时 raise，dest 原文不动。"""
    import personal_assistant.config.local_store as ls
    import os
    import stat

    main_cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(ls, "default_local_config_path", lambda: main_cfg.resolve())

    cfg = _make_minimal_config(tmp_path)
    original_text = "# original\n"
    main_cfg.write_text(original_text, encoding="utf-8")

    # 创建 backups/ 但去掉写权限
    backups_dir = main_cfg.parent / "backups"
    backups_dir.mkdir()
    backups_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x，无写权限

    try:
        with pytest.raises(Exception):
            save_local_config(cfg, main_cfg)

        # dest 内容不变
        assert main_cfg.read_text(encoding="utf-8") == original_text, "备份失败时 dest 不应被改动"
    finally:
        # 恢复权限让 tmp_path 清理能成功
        backups_dir.chmod(stat.S_IRWXU)
