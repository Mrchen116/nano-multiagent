import pytest

from nano_multiagent.cli.managed_server import ManagedServerConfig, ManagedServerError, ManagedServerProcess


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


def test_managed_server_rejects_non_local_base_url() -> None:
    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://api.example.com:9000", token="test-token"),
    )

    with pytest.raises(ManagedServerError, match="managed mode requires a local --base-url"):
        manager.start()


def test_managed_server_reports_port_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nano_multiagent.cli.managed_server._is_port_in_use", lambda host, port: True)
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
    monkeypatch.setattr("nano_multiagent.cli.managed_server._is_port_in_use", lambda host, port: False)
    process = _FakeProcess()

    manager = ManagedServerProcess(
        config=ManagedServerConfig(base_url="http://127.0.0.1:8123", token="test-token"),
        popen_factory=lambda *args, **kwargs: process,
        health_probe=lambda _: True,
    )

    manager.start()
    manager.stop()

    assert process.terminated is True
