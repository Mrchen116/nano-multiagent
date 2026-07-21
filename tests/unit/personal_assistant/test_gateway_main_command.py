"""Unit tests for the main() CLI entry point: background/foreground dispatch and error handling."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.gateway.im_bootstrap import GatewayStartupError
from personal_assistant.gateway.process_lifecycle import BackgroundLaunchResult
from personal_assistant.main import main


def test_main_defaults_to_background_launch(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}
    result = BackgroundLaunchResult(
        pid=999,
        log_path=tmp_path / "gateway.log",
    )

    def _launch_background(
        *, config_path: str, im_service_url_override: str | None = None
    ) -> BackgroundLaunchResult:
        seen["background"] = (config_path, im_service_url_override)
        return result

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        _launch_background,
    )
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.run_gateway",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("foreground path should not run")
        ),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert seen == {"background": (str(tmp_path / "node-config.yaml"), None)}
    assert capsys.readouterr().out == (
        f"Gateway started (pid=999)\nLog:             {tmp_path / 'gateway.log'}\n"
    )


def test_main_passes_im_service_url_override_to_background_launch(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def _launch_background(**kwargs):  # noqa: ANN001
        seen.update(kwargs)
        return BackgroundLaunchResult(
            pid=1,
            log_path=tmp_path / "gateway.log",
            im_service_url="http://im.remote:9011",
        )

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        _launch_background,
    )
    monkeypatch.setattr(
        "personal_assistant.main._check_im_reachable", lambda _url: False
    )
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.run_gateway",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("foreground path should not run")
        ),
    )

    exit_code = main(
        [
            "--config",
            str(tmp_path / "node-config.yaml"),
            "--im-service-url",
            "http://im.remote:9011",
        ]
    )

    assert exit_code == 0
    assert seen == {
        "config_path": str(tmp_path / "node-config.yaml"),
        "im_service_url_override": "http://im.remote:9011",
    }
    assert capsys.readouterr().out == (
        "Gateway started (pid=1)\n"
        "IM service:      http://im.remote:9011  "
        "[unavailable (running offline, will retry)]\n"
        f"Log:             {tmp_path / 'gateway.log'}\n"
    )


def test_main_defaults_to_canonical_config_path_when_flag_missing(
    monkeypatch, tmp_path: Path
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    seen: dict[str, object] = {}

    def _launch_background(**kwargs):  # noqa: ANN001
        seen["background"] = kwargs["config_path"]
        return BackgroundLaunchResult(
            pid=1,
            log_path=tmp_path / "gateway.log",
        )

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        _launch_background,
    )
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.run_gateway",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("foreground path should not run")
        ),
    )

    exit_code = main([])

    assert exit_code == 0
    assert seen == {
        "background": str((home_dir / ".nano-assistant" / "config.yaml").resolve())
    }


def test_main_runs_gateway_in_foreground_when_requested(
    monkeypatch, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def _run_gateway(
        *, config_path: str, factories=None, im_service_url_override: str | None = None
    ) -> int:  # noqa: ANN001
        seen["foreground"] = (config_path, factories, im_service_url_override)
        return 0

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.run_gateway", _run_gateway
    )
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("background path should not run")
        ),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml"), "--foreground"])

    assert exit_code == 0
    assert seen == {"foreground": (str(tmp_path / "node-config.yaml"), None, None)}


def test_main_passes_im_service_url_override_to_foreground_run(
    monkeypatch, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def _run_gateway(
        *, config_path: str, factories=None, im_service_url_override: str | None = None
    ) -> int:  # noqa: ANN001
        seen["foreground"] = (config_path, factories, im_service_url_override)
        return 0

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.run_gateway", _run_gateway
    )
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("background path should not run")
        ),
    )

    exit_code = main(
        [
            "--config",
            str(tmp_path / "node-config.yaml"),
            "--im-service-url",
            "http://im.remote:9011",
            "--foreground",
        ]
    )

    assert exit_code == 0
    assert seen == {
        "foreground": (
            str(tmp_path / "node-config.yaml"),
            None,
            "http://im.remote:9011",
        )
    }


def test_main_returns_non_zero_when_background_launch_fails(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("gateway failed")),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 1
    assert capsys.readouterr().err == "ERROR gateway failed\n"


def test_main_surfaces_next_step_for_gateway_startup_error(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(
            GatewayStartupError(
                summary="node-local did not appear in IM bootstrap",
                next_step="Verify /im/v1/nodes on the configured IM API and rerun gateway.",
            )
        ),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 1
    assert capsys.readouterr().err == (
        "Gateway failed to start\n\n"
        "  node-local did not appear in IM bootstrap\n\n"
        "  → Verify /im/v1/nodes on the configured IM API and rerun gateway.\n"
    )


def test_main_stop_command_stops_background_gateway(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def _stop_background(*, config_path: str) -> str:
        seen["config_path"] = config_path
        return "STOPPED pid=999"

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.stop_gateway", _stop_background
    )

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert seen == {"config_path": str(tmp_path / "node-config.yaml")}
    assert capsys.readouterr().out == "STOPPED pid=999\n"


def test_main_stop_command_defaults_to_canonical_config_path_when_flag_missing(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    seen: dict[str, object] = {}

    def _stop_background(*, config_path: str) -> str:
        seen["config_path"] = config_path
        return "STOPPED pid=999"

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.stop_gateway", _stop_background
    )

    exit_code = main(["stop"])

    assert exit_code == 0
    assert seen == {
        "config_path": str((home_dir / ".nano-assistant" / "config.yaml").resolve())
    }
    assert capsys.readouterr().out == "STOPPED pid=999\n"


def test_main_stop_command_reports_not_running(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.stop_gateway",
        lambda **_kwargs: "NOT RUNNING config=node-config.yaml",
    )

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert capsys.readouterr().out == "NOT RUNNING config=node-config.yaml\n"


def test_main_stop_command_reports_stale_runtime_state(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.stop_gateway",
        lambda **_kwargs: "STALE pid=999 state=.gateway-state.json",
    )

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert capsys.readouterr().out == "STALE pid=999 state=.gateway-state.json\n"


def test_main_restart_command_uses_serialized_lifecycle_operation(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def _restart(
        *, config_path: str, im_service_url_override: str | None = None
    ) -> BackgroundLaunchResult:
        seen.update(
            config_path=config_path,
            im_service_url_override=im_service_url_override,
        )
        return BackgroundLaunchResult(
            pid=1234,
            log_path=tmp_path / "gateway.log",
        )

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.restart_gateway", _restart
    )

    config_path = str(tmp_path / "node-config.yaml")
    exit_code = main(["restart", "--config", config_path])

    assert exit_code == 0
    assert seen == {
        "config_path": config_path,
        "im_service_url_override": None,
    }
    out = capsys.readouterr().out
    assert "Gateway started (pid=1234)" in out
