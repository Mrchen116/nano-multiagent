import io

import pytest

from coding_cli.managed_server import ManagedServerConfig, ManagedServerError, ManagedServerProcess


class _FakeProcess:
    def __init__(self, *, return_code: int | None = None) -> None:
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = 0

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.return_code is None:
            self.return_code = 0
        return self.return_code

    def kill(self) -> None:
        self.killed = True
        self.return_code = -9


class _ExitedProcess(_FakeProcess):
    def __init__(self) -> None:
        super().__init__(return_code=1)
        self.stderr = io.StringIO("startup failed")


def test_managed_server_rejects_non_local_base_url() -> None:
    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://api.example.com:9000", token="test-token"),
    )

    with pytest.raises(ManagedServerError, match="managed mode requires a local --base-url"):
        manager.start()


def test_managed_server_reports_port_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: True)
    popen_called = False

    def _popen(*args, **kwargs):
        del args, kwargs
        nonlocal popen_called
        popen_called = True
        return _FakeProcess()

    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://127.0.0.1:8122", token="test-token"),
        popen_factory=_popen,
    )

    with pytest.raises(ManagedServerError, match="port 8122"):
        manager.start()
    assert popen_called is False


def test_managed_server_start_and_stop_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _FakeProcess()

    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://127.0.0.1:8123", token="test-token"),
        popen_factory=lambda *args, **kwargs: process,
        health_probe=lambda _: True,
    )

    manager.start()
    manager.stop()

    assert process.terminated is True



def test_managed_server_uses_platform_http_api_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _FakeProcess()
    captured_command: list[str] = []

    def _popen(command, **kwargs):  # noqa: ANN001, ANN003
        del kwargs
        captured_command.extend(command)
        return process

    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://127.0.0.1:8127", token="test-token"),
        popen_factory=_popen,
        health_probe=lambda _: True,
    )

    manager.start()
    manager.stop()

    assert "coding_cli.kernel_app:app" in captured_command


def test_managed_server_reports_startup_timeout_with_suggestion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _FakeProcess()
    times = iter([0.0, 0.05, 0.2])

    manager = ManagedServerProcess(
        config=ManagedServerConfig(
            base_url="http://127.0.0.1:8124",
            token="test-token",
            startup_timeout_seconds=0.1,
            poll_interval_seconds=0.01,
        ),
        popen_factory=lambda *args, **kwargs: process,
        health_probe=lambda _: False,
        time_fn=lambda: next(times),
        sleep_fn=lambda _: None,
    )

    with pytest.raises(ManagedServerError, match="startup timed out") as exc_info:
        manager.start()
    assert exc_info.value.suggestion is not None
    assert "switch to --mode remote" in exc_info.value.suggestion
    assert process.terminated is True


def test_managed_server_reports_startup_exit_with_suggestion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _ExitedProcess()

    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://127.0.0.1:8125", token="test-token"),
        popen_factory=lambda *args, **kwargs: process,
        health_probe=lambda _: False,
    )

    with pytest.raises(ManagedServerError, match="exited before becoming healthy") as exc_info:
        manager.start()
    assert exc_info.value.suggestion is not None
    assert "check local api logs" in exc_info.value.suggestion.lower()


def test_managed_server_injects_llm_env_into_managed_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("coding_cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _FakeProcess()
    captured_env: dict[str, str] = {}

    def _popen(*args, **kwargs):  # noqa: ANN002, ANN003
        del args
        env = kwargs.get("env")
        if isinstance(env, dict):
            captured_env.update(env)
        return process

    manager = ManagedServerProcess(
        config=ManagedServerConfig(
            base_url="http://127.0.0.1:8126",
            token="test-token",
            llm_provider="anthropic",
            llm_model="claude-3-5-sonnet-20241022",
            llm_base_url="http://127.0.0.1:4100",
            llm_api_key="sk-managed",
            llm_timeout_seconds=55.0,
        ),
        popen_factory=_popen,
        health_probe=lambda _: True,
    )

    manager.start()
    manager.stop()

    assert captured_env["NANO_MULTIAGENT_API_TOKEN"] == "test-token"
    assert captured_env["NANO_MULTIAGENT_LLM_PROVIDER"] == "anthropic"
    assert captured_env["NANO_MULTIAGENT_LLM_MODEL"] == "claude-3-5-sonnet-20241022"
    assert captured_env["NANO_MULTIAGENT_LLM_BASE_URL"] == "http://127.0.0.1:4100"
    assert captured_env["NANO_MULTIAGENT_LLM_API_KEY"] == "sk-managed"
    assert captured_env["NANO_MULTIAGENT_LLM_TIMEOUT_SECONDS"] == "55.0"
