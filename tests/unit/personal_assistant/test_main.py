from pathlib import Path

import pytest

from personal_assistant.config.local_store import KernelConfig, LocalConfig, NodeConfig
from personal_assistant.main import GatewayProcessManager, GatewayRuntime, RuntimeFactories, run_gateway


class _FakeKernelClient:
    def __init__(self, health_results: list[dict[str, object] | Exception]) -> None:
        self.health_results = list(health_results)
        self.calls = 0

    def health(self) -> dict[str, object]:
        self.calls += 1
        outcome = self.health_results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeProcess:
    def __init__(self, wait_result: int | TimeoutError) -> None:
        self.wait_result = wait_result
        self.terminate_called = 0
        self.kill_called = 0
        self.wait_calls: list[float] = []

    def terminate(self) -> None:
        self.terminate_called += 1

    def kill(self) -> None:
        self.kill_called += 1

    def wait(self, timeout: float) -> int:
        self.wait_calls.append(timeout)
        if isinstance(self.wait_result, TimeoutError):
            raise self.wait_result
        return self.wait_result


def _build_config(tmp_path: Path) -> LocalConfig:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    return LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(),
        channels=(),
        kernel=KernelConfig(
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )


def test_gateway_process_manager_waits_for_kernel_health(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    client = _FakeKernelClient([RuntimeError("not ready"), {"healthy": True}])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: 0.0 if client.calls == 0 else 0.05 * client.calls,
        sleep=lambda _: None,
    )

    manager.start_kernel_process()

    assert client.calls == 2
    assert manager.process is process


def test_gateway_process_manager_raises_when_health_never_becomes_ready(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    client = _FakeKernelClient([RuntimeError("down"), RuntimeError("down"), RuntimeError("down")])
    times = iter([0.0, 0.05, 0.15, 0.25])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: next(times),
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="kernel health check timed out"):
        manager.start_kernel_process()


def test_gateway_process_manager_shutdown_uses_kill_after_terminate_timeout(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=TimeoutError())
    client = _FakeKernelClient([{"healthy": True}])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    manager.start_kernel_process()

    manager.stop_kernel_process()

    assert process.terminate_called == 1
    assert process.kill_called == 1
    assert process.wait_calls == [0.1]


def test_run_gateway_loads_config_and_starts_runtime(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    seen: dict[str, object] = {}

    class _Runtime:
        def __init__(self, loaded_config: LocalConfig) -> None:
            seen["config"] = loaded_config

        def run_forever(self) -> int:
            seen["ran"] = True
            return 0

    exit_code = run_gateway(
        config_path=tmp_path / "node-config.yaml",
        factories=RuntimeFactories(
            load_config=lambda path: config if path == tmp_path / "node-config.yaml" else None,
            build_runtime=lambda loaded_config: _Runtime(loaded_config),
        ),
    )

    assert exit_code == 0
    assert seen == {"config": config, "ran": True}
