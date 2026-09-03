"""Gateway lifecycle policy across LaunchAgent and detached modes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.gateway import process_lifecycle

from ._main_helpers import _FakeProcess, build_config


@pytest.fixture(autouse=True)
def _assume_launch_agent_is_not_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "is_loaded",
        lambda **_kwargs: False,
    )


def _publish_state(config_path: Path, *, pid: int, process_start: str) -> None:
    (config_path.parent / ".gateway-state.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "process_start": process_start,
                "config_path": str(config_path.resolve()),
                "log_path": str(config_path.parent / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )


def test_macos_default_start_uses_launch_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=True))
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle, "_process_start_identity", lambda _pid: "birth"
    )

    def apply(**kwargs: object) -> None:
        calls.append(dict(kwargs))
        _publish_state(config.source_path, pid=4321, process_start="birth")

    monkeypatch.setattr(process_lifecycle.macos_launch_agent, "apply_and_start", apply)

    result = process_lifecycle.launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        auto_bind=True,
        im_service_url_override="http://im.once:8011",
    )

    assert result.autostart_status == "enabled"
    assert result.pid == 4321
    assert calls[0]["auto_bind"] is True
    assert calls[0]["im_service_url_override"] == "http://im.once:8011"


def test_non_macos_keeps_detached_mode_and_marks_autostart_not_applicable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    monkeypatch.setattr(process_lifecycle.sys, "platform", "linux")
    monkeypatch.setattr(
        process_lifecycle, "_process_start_identity", lambda _pid: "birth"
    )
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "apply_and_start",
        lambda **_kwargs: pytest.fail("non-macOS must not call launchctl"),
    )

    def publish(_child, _config, _timeout) -> None:  # noqa: ANN001
        _publish_state(config.source_path, pid=2468, process_start="birth")

    result = process_lifecycle.launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=lambda _argv, _log_path: process,
        wait_for_start=publish,
    )

    assert result.autostart_status == "not_applicable"


def test_macos_start_rejects_loaded_launch_agent_before_state_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = build_config(tmp_path)
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "is_loaded",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "apply_and_start",
        lambda **_kwargs: pytest.fail("bare start must preserve the loaded service"),
    )

    with pytest.raises(process_lifecycle.GatewayStartupError, match="already running"):
        process_lifecycle.launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
        )


def test_launch_agent_failure_rolls_back_then_runs_one_detached_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=True))
    process = _FakeProcess(wait_result=0, pid=2468)
    events: list[str] = []
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle, "_process_start_identity", lambda _pid: "birth"
    )
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "apply_and_start",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bootstrap denied")),
    )
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "permanently_remove",
        lambda **_kwargs: events.append("rollback"),
    )

    def spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        events.append("detached")
        return process

    def publish(_child, _config, _timeout) -> None:  # noqa: ANN001
        _publish_state(config.source_path, pid=2468, process_start="birth")

    result = process_lifecycle.launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=spawn,
        wait_for_start=publish,
    )

    assert events == ["rollback", "detached"]
    assert result.autostart_status == "failed"
    assert result.autostart_error == "bootstrap denied"


def test_launch_agent_rollback_failure_does_not_start_detached_gateway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=True))
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "apply_and_start",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bootstrap denied")),
    )
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "permanently_remove",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bootout denied")),
    )

    with pytest.raises(
        process_lifecycle.GatewayStartupError, match="rollback also failed"
    ):
        process_lifecycle.launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda *_args: pytest.fail(
                "must not start detached fallback"
            ),
        )


def test_disable_failure_does_not_start_detached_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=False))
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "permanently_remove",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("remove denied")),
    )

    with pytest.raises(RuntimeError, match="remove denied"):
        process_lifecycle.launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda *_args: pytest.fail("must not start replacement"),
        )


def test_run_gateway_applies_explicit_cli_control_after_config_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(
        base,
        gateway=replace(
            base.gateway,
            environment={
                "SEARXNG_URL": "http://config-searxng",
                "NANO_MULTIAGENT_AUTO_BIND": "0",
            },
        ),
    )
    seen: dict[str, str | None] = {}
    monkeypatch.setenv("SEARXNG_URL", "http://inherited-searxng")
    monkeypatch.setenv("NANO_MULTIAGENT_AUTO_BIND", "inherited")

    class _Runtime:
        def run_forever(self) -> int:
            seen["searxng"] = process_lifecycle.os.environ.get("SEARXNG_URL")
            seen["auto_bind"] = process_lifecycle.os.environ.get(
                "NANO_MULTIAGENT_AUTO_BIND"
            )
            return 0

    process_lifecycle.run_gateway(
        config_path=config.source_path,
        factories=process_lifecycle.RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
        auto_bind=True,
    )

    assert seen == {
        "searxng": "http://config-searxng",
        "auto_bind": "1",
    }


def test_run_gateway_process_identity_ignores_configured_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(
        base,
        gateway=replace(base.gateway, environment={"PATH": "/gateway/tools"}),
    )
    monkeypatch.setenv("PATH", "/inherited/tools")
    monkeypatch.setattr(
        process_lifecycle, "install_builtin_skills_for_gateway", lambda: None
    )

    class _Runtime:
        def run_forever(self) -> int:
            return 0

    result = process_lifecycle.run_gateway(
        config_path=config.source_path,
        factories=process_lifecycle.RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
    )

    assert result == 0


def test_managed_stop_boots_out_before_process_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=True))
    running = True
    events: list[str] = []
    _publish_state(config.source_path, pid=4321, process_start="birth")
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")

    def stop_service(**_kwargs: object) -> bool:
        nonlocal running
        events.append("bootout")
        running = False
        return True

    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent, "stop_current_login", stop_service
    )
    monkeypatch.setattr(
        process_lifecycle,
        "_process_start_identity",
        lambda _pid: "birth" if running else None,
    )
    monkeypatch.setattr(
        process_lifecycle.os,
        "killpg",
        lambda *_args: pytest.fail("bootout already stopped the managed process"),
    )

    result = process_lifecycle.stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert events == ["bootout"]
    assert result.startswith("STOPPED pid=4321")


def test_managed_stop_failure_does_not_signal_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = build_config(tmp_path)
    config = replace(base, gateway=replace(base.gateway, autostart=True))
    _publish_state(config.source_path, pid=4321, process_start="birth")
    monkeypatch.setattr(process_lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(
        process_lifecycle.macos_launch_agent,
        "stop_current_login",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bootout denied")),
    )
    monkeypatch.setattr(
        process_lifecycle.os,
        "killpg",
        lambda *_args: pytest.fail("bootout failure must stop before signalling"),
    )

    with pytest.raises(RuntimeError, match="bootout denied"):
        process_lifecycle.stop_gateway(
            config_path=config.source_path, load_config=lambda _path: config
        )
