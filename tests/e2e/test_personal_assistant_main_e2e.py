from pathlib import Path

from personal_assistant.main import run_gateway


def test_run_gateway_e2e_starts_runtime_with_loaded_config(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-e2e",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
                "kernel:",
                "  command: python -m agent.platform.http_api.app",
            ]
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    class _Runtime:
        def __init__(self, config) -> None:  # noqa: ANN001
            seen["node_id"] = config.node.node_id
            seen["health_path"] = config.kernel.health_path

        def run_forever(self) -> int:
            seen["started"] = True
            return 0

    exit_code = run_gateway(
        config_path=config_path,
        factories={"build_runtime": _Runtime},
    )

    assert exit_code == 0
    assert seen == {"node_id": "node-e2e", "health_path": "/v1/health", "started": True}
