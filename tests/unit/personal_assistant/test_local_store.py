from pathlib import Path

import pytest

from personal_assistant.config.local_store import DEFAULT_LOCAL_KERNEL_TOKEN, default_local_config_path, load_local_config, save_local_config


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
        ),
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
        ),
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
        ),
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
        ),
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
        ),
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
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert [agent.agent_id for agent in config.agents] == ["Alpha", "Beta"]
    assert [agent.title for agent in config.agents] == ["Alpha", "Beta"]
    assert [agent.workspace_root for agent in config.agents] == [alpha_root, beta_root]


def test_load_local_config_uses_internal_kernel_base_url_default(tmp_path: Path) -> None:
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
                "  command: python -m agent.platform.http_api.app",
            ]
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.kernel.base_url == "http://127.0.0.1:8000"
    assert config.kernel.command == "python -m agent.platform.http_api.app"
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
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.kernel.command == "python -m uvicorn personal_assistant.kernel_app:app"
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
        ),
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
        ),
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
        ),
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
        ),
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
        ),
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
                "    default_model: gpt-4",
            ]
        ),
        encoding="utf-8",
    )

    config = load_local_config(config_path)
    agent = config.agents[0]

    assert agent.system_prompt == "You are a helpful assistant."
    assert agent.skills == ("web_search", "code_review")
    assert agent.tool_allowlist == ("Read", "Write")
    assert agent.group_reply_policy == "always"
    assert agent.default_model == "gpt-4"


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
                "    default_model: gpt-4",
                "channels:",
                "  - name: web_relay",
                "    enabled: true",
                "    settings:",
                "      port: 8080",
                "im_service:",
                "  url: wss://im.example.com",
                "  token: secret-token",
            ]
        ),
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
        ),
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
        ),
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
        ),
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
        ),
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
