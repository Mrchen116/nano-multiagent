"""Process entry for the personal assistant Node Gateway skeleton."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import httpx

from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
from personal_assistant.config.local_store import KernelConfig, LocalConfig, load_local_config


ProcessLike = subprocess.Popen[Any]
ProcessFactory = Callable[[str], ProcessLike]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class RuntimeFactories:
    """Collect replaceable construction hooks used by the gateway entry.

    Args:
        load_config: Function used to load YAML config into `LocalConfig`.
        build_runtime: Factory that creates the runtime orchestrator from config.
    """

    load_config: Callable[[str | Path], LocalConfig] = load_local_config
    build_runtime: Callable[[LocalConfig], "GatewayRuntime"] | None = None


class GatewayProcessManager:
    """Manage the local agent kernel child process for the gateway.

    Args:
        config: Kernel process and health-probe settings loaded from local config.
        kernel_client: HTTP client used for readiness probes.
        process_factory: Factory used to spawn the kernel child process.
        monotonic: Monotonic clock source for timeout accounting.
        sleep: Sleep function used between readiness probes.
    """

    def __init__(
        self,
        *,
        config: KernelConfig,
        kernel_client: KernelApiClient,
        process_factory: ProcessFactory | None = None,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._config = config
        self._kernel_client = kernel_client
        self._process_factory = process_factory or _spawn_process
        self._monotonic = monotonic
        self._sleep = sleep
        self.process: ProcessLike | None = None

    def start_kernel_process(self) -> ProcessLike:
        """Spawn the local kernel child and wait until `/v1/health` reports ready.

        Returns:
            The spawned process handle once health probing succeeds.

        Raises:
            RuntimeError: When the kernel does not become healthy before timeout.

        Side Effects:
            Starts a subprocess and performs repeated HTTP health checks.
        """

        if self.process is not None:
            return self.process
        process = self._process_factory(self._config.command)
        self.process = process
        self._wait_for_health()
        return process

    def stop_kernel_process(self) -> None:
        """Terminate the managed kernel child, escalating to kill when needed.

        Side Effects:
            Sends terminate/kill signals to the managed child process.
        """

        process = self.process
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._config.shutdown_grace_seconds)
        except TimeoutError:
            process.kill()
        finally:
            self.process = None

    def _wait_for_health(self) -> None:
        deadline = self._monotonic() + self._config.startup_timeout_seconds
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            try:
                payload = self._kernel_client.health()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            else:
                if bool(payload.get("healthy")):
                    return
                last_error = RuntimeError(f"kernel reported unhealthy payload: {payload}")
            self._sleep(self._config.health_poll_interval_seconds)
        message = "kernel health check timed out"
        if last_error is not None:
            raise RuntimeError(message) from last_error
        raise RuntimeError(message)


class GatewayRuntime:
    """Run the minimal M98 gateway lifecycle around the local kernel.

    Args:
        config: Parsed immutable local gateway config.
        process_manager: Kernel child-process lifecycle manager.
    """

    def __init__(self, config: LocalConfig, process_manager: GatewayProcessManager) -> None:
        self._config = config
        self._process_manager = process_manager

    def run_forever(self) -> int:
        """Start the managed kernel, then immediately perform shutdown cleanup.

        Notes:
            M98 only needs startup/health-check/teardown skeletons. Future milestones
            will keep the process alive to host channels, schedulers, and upstream IO.
        """

        self._process_manager.start_kernel_process()
        self._process_manager.stop_kernel_process()
        return 0


def run_gateway(
    *,
    config_path: str | Path,
    factories: RuntimeFactories | Mapping[str, Any] | None = None,
) -> int:
    """Load config, build runtime, and execute the gateway entry flow.

    Args:
        config_path: YAML config file passed by the operator.
        factories: Optional factory overrides used by tests.

    Returns:
        Process exit code. `0` means the managed startup/shutdown sequence succeeded.
    """

    resolved_factories = _coerce_factories(factories)
    config = resolved_factories.load_config(config_path)
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    return runtime.run_forever()


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default M98 gateway runtime from parsed local config."""

    kernel_client = KernelApiClient(
        config=KernelApiClientConfig(
            base_url=config.kernel.base_url,
            token=config.kernel.token,
            request_id=config.kernel.request_id,
            timeout_seconds=config.kernel.timeout_seconds,
        )
    )
    manager = GatewayProcessManager(config=config.kernel, kernel_client=kernel_client)
    return GatewayRuntime(config, manager)


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""

    parser = argparse.ArgumentParser(description="Run personal assistant gateway skeleton")
    parser.add_argument("--config", required=True, help="Path to local node-config.yaml")
    args = parser.parse_args(argv)
    return run_gateway(config_path=args.config)


def _coerce_factories(factories: RuntimeFactories | Mapping[str, Any] | None) -> RuntimeFactories:
    if factories is None:
        return RuntimeFactories()
    if isinstance(factories, RuntimeFactories):
        return factories
    load_config = factories.get("load_config", load_local_config)
    build_runtime_factory = factories.get("build_runtime")
    return RuntimeFactories(load_config=load_config, build_runtime=build_runtime_factory)


def _spawn_process(command: str) -> ProcessLike:
    return subprocess.Popen(shlex.split(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())
