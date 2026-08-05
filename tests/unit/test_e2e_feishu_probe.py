"""Focused tests for the Feishu E2E probe target guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e-feishu-probe.py"


@pytest.fixture
def probe_module(monkeypatch: pytest.MonkeyPatch):
    """Load the executable probe while preserving its script-local imports."""
    monkeypatch.syspath_prepend(str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("e2e_feishu_probe", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_rejects_non_feishu_stack_before_sending(
    tmp_path: Path, probe_module: object
) -> None:
    """A default E2E worktree cannot be used as a Feishu message target."""
    (tmp_path / ".e2e-ports.env").write_text(
        "export E2E_PROFILE=default\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="not started with --feishu"):
        probe_module._require_feishu_stack(tmp_path)


def test_probe_accepts_feishu_stack_marker(
    tmp_path: Path, probe_module: object
) -> None:
    """The launcher marker admits only a worktree started with --feishu."""
    (tmp_path / ".e2e-ports.env").write_text(
        "export E2E_PROFILE=feishu\n", encoding="utf-8"
    )

    probe_module._require_feishu_stack(tmp_path)


def test_probe_default_env_path_honors_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, probe_module: object
) -> None:
    """The probe follows the launcher's XDG private-profile location."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert probe_module._default_e2e_env_path() == (
        tmp_path / "nano-multiagent" / "feishu-e2e.env"
    )
