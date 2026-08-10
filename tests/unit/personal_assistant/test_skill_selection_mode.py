from pathlib import Path

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    load_local_config,
    save_local_config,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_composition import project_agent_runtime


def _snapshot(tmp_path: Path, *, skills: tuple[str, ...], mode: str | None):
    return LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="a",
                workspace_root=tmp_path / "ws",
                skills=skills,
                skills_selection_mode=mode,
            ),
        )
    ).require("a")


def test_runtime_preserves_explicit_empty_allowlist(tmp_path: Path) -> None:
    runtime = project_agent_runtime(
        _snapshot(tmp_path, skills=(), mode="explicit_allowlist"),
        scenario={},
        resolved_model="test-model",
    ).runtime
    assert runtime.skills == []


def test_runtime_keeps_legacy_empty_as_default_discovery(tmp_path: Path) -> None:
    runtime = project_agent_runtime(
        _snapshot(tmp_path, skills=(), mode=None),
        scenario={},
        resolved_model="test-model",
    ).runtime
    assert runtime.skills is None


def test_explicit_empty_round_trips_gateway_yaml(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    source.write_text(
        """llm:\n  default_model: p:m\n  providers:\n    - name: p\n      base_url: http://localhost\n      models:\n        - name: p:m\nnode:\n  node_id: n\nagents:\n  - agent_id: a\n"""
        f"    workspace_root: {workspace}\n"
        "    skills: []\n    skills_selection_mode: explicit_allowlist\n",
        encoding="utf-8",
    )
    config = load_local_config(source)
    output = tmp_path / "output.yaml"
    save_local_config(config, output)
    reloaded = load_local_config(output).agents[0]
    assert reloaded.skills == ()
    assert reloaded.skills_selection_mode == "explicit_allowlist"
