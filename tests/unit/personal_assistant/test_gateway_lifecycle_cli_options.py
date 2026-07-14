"""Regression coverage for lifecycle CLI target-option parsing."""

from __future__ import annotations

import os
from pathlib import Path

from personal_assistant.main import BackgroundLaunchResult, main


def test_global_options_before_restart_preserve_lifecycle_target(
    monkeypatch, tmp_path: Path
) -> None:
    """Global-first restart keeps its target and scopes auto-bind to one launch."""
    calls: list[tuple[str, str, str | None]] = []
    observed_auto_bind: list[str | None] = []
    config_path = str(tmp_path / "isolated-config.yaml")
    im_service_url = "http://127.0.0.1:59123"
    second_config_path = str(tmp_path / "second-isolated-config.yaml")
    second_im_service_url = "http://127.0.0.1:59124"
    original_auto_bind = os.environ.pop("NANO_MULTIAGENT_AUTO_BIND", None)

    def _stop(*, config_path: str) -> str:
        calls.append(("stop", config_path, None))
        return "NOT RUNNING"

    def _start(
        *, config_path: str, im_service_url_override: str | None = None
    ) -> BackgroundLaunchResult:
        observed_auto_bind.append(os.environ.get("NANO_MULTIAGENT_AUTO_BIND"))
        calls.append(("start", config_path, im_service_url_override))
        return BackgroundLaunchResult(pid=1234, log_path=tmp_path / "gateway.log")

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop)
    monkeypatch.setattr("personal_assistant.main.launch_gateway_in_background", _start)

    try:
        assert (
            main(
                [
                    "--config",
                    config_path,
                    "--im-service-url",
                    im_service_url,
                    "--auto-bind",
                    "restart",
                ]
            )
            == 0
        )
        assert calls == [
            ("stop", config_path, None),
            ("start", config_path, im_service_url),
        ]
        assert observed_auto_bind == ["1"]
        assert "NANO_MULTIAGENT_AUTO_BIND" not in os.environ

        assert (
            main(
                [
                    "--config",
                    second_config_path,
                    "--im-service-url",
                    second_im_service_url,
                    "restart",
                ]
            )
            == 0
        )
        assert calls == [
            ("stop", config_path, None),
            ("start", config_path, im_service_url),
            ("stop", second_config_path, None),
            ("start", second_config_path, second_im_service_url),
        ]
        assert observed_auto_bind == ["1", None]
        assert "NANO_MULTIAGENT_AUTO_BIND" not in os.environ
    finally:
        if original_auto_bind is None:
            os.environ.pop("NANO_MULTIAGENT_AUTO_BIND", None)
        else:
            os.environ["NANO_MULTIAGENT_AUTO_BIND"] = original_auto_bind


def test_global_config_before_stop_preserves_lifecycle_target(
    monkeypatch, tmp_path: Path
) -> None:
    """Global-first stop must only manage the explicitly selected Gateway."""
    config_path = str(tmp_path / "isolated-config.yaml")
    seen: list[str] = []

    def _stop(*, config_path: str) -> str:
        seen.append(config_path)
        return "NOT RUNNING"

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop)

    assert main(["--config", config_path, "stop"]) == 0
    assert seen == [config_path]
