"""Focused regressions for the dedicated Feishu self-evolution journey."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml


_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "e2e-feishu-self-evolution.py"
_DOWN = _ROOT / "scripts" / "e2e-down.sh"


@pytest.fixture
def journey_module(monkeypatch: pytest.MonkeyPatch):
    """Load the executable journey while preserving its script-local imports."""
    monkeypatch.syspath_prepend(str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("e2e_feishu_self_evolution", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_gateway_config(path: Path, base_url: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "node": {"node_id": "wt-test"},
                "llm": {
                    "providers": [
                        {
                            "name": "anthropic",
                            "base_url": base_url,
                            "models": [{"id": "test"}],
                        }
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_restart_rewrites_fixture_route_after_original_gateway_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journey_module: object
) -> None:
    """A draining old Gateway cannot restore its production LLM after the rewrite."""
    config_path = tmp_path / ".gateway-config.yaml"
    fixture_url = "http://127.0.0.1:19996"
    production_url = "http://127.0.0.1:4000"
    _write_gateway_config(config_path, fixture_url)
    (tmp_path / ".gateway.pid").write_text("42\n", encoding="utf-8")
    (tmp_path / ".e2e-ports.env").write_text(
        "export IM_URL=http://127.0.0.1:54321\n", encoding="utf-8"
    )

    def fake_kill(pid: int, sig: int) -> None:
        assert pid == 42
        if sig == signal.SIGTERM:
            # The old process still owns a production-valued immutable snapshot and
            # may persist it while draining the probe run.
            _write_gateway_config(config_path, production_url)
            return
        if sig == 0:
            raise ProcessLookupError
        raise AssertionError(sig)

    class SpawnObserved(RuntimeError):
        pass

    def fake_popen(*_args: object, **_kwargs: object) -> None:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert payload["llm"]["providers"][0]["base_url"] == fixture_url
        raise SpawnObserved

    monkeypatch.setattr(journey_module.os, "kill", fake_kill)
    monkeypatch.setattr(journey_module.subprocess, "Popen", fake_popen)

    with pytest.raises(SpawnObserved):
        journey_module._restart_gateway(tmp_path, fixture_url)


@pytest.mark.parametrize("journey_error", [None, RuntimeError("controlled failure")])
def test_main_removes_fixture_record_after_success_or_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    journey_module: object,
    journey_error: RuntimeError | None,
) -> None:
    """The fixture JSONL is worktree runtime and never survives the journey."""
    (tmp_path / ".e2e-ports.env").write_text(
        "export E2E_PROFILE=feishu\n", encoding="utf-8"
    )
    env_path = tmp_path / "feishu.env"
    env_path.write_text("private fixture placeholder\n", encoding="utf-8")
    record_path = tmp_path / ".feishu-self-evolution-llm.jsonl"
    process = SimpleNamespace()

    def start_fixture(worktree: Path) -> tuple[object, str]:
        assert worktree == tmp_path
        record_path.write_text("controlled request\n", encoding="utf-8")
        return process, "http://127.0.0.1:19996"

    def run_journey(*_args: object, **_kwargs: object) -> dict[str, str]:
        if journey_error is not None:
            raise journey_error
        return {"nonce": "test"}

    monkeypatch.setattr(
        sys, "argv", [str(_SCRIPT), "--wt", str(tmp_path), "--env", str(env_path)]
    )
    monkeypatch.setattr(
        journey_module,
        "load_e2e_env",
        lambda _path: {
            "NANO_MULTIAGENT_E2E_FEISHU_LARK_PROFILE": "dedicated",
            "NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID": "ou_bot",
        },
    )
    monkeypatch.setattr(
        journey_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "verified": True,
                    "appId": None,
                    "identities": {"bot": {"verified": True, "openId": "ou_bot"}},
                }
            ),
        ),
    )
    monkeypatch.setattr(journey_module, "_require_test_profile", lambda *_: None)
    monkeypatch.setattr(journey_module, "_start_fixture", start_fixture)
    monkeypatch.setattr(journey_module, "_run_journey", run_journey)
    monkeypatch.setattr(journey_module, "_stop_process", lambda value: value is process)

    if journey_error is None:
        assert journey_module.main() == 0
    else:
        with pytest.raises(RuntimeError, match="controlled failure"):
            journey_module.main()
    assert not record_path.exists()


def test_e2e_down_removes_self_evolution_runtime_artifacts(tmp_path: Path) -> None:
    """The public stack teardown removes receipts and controlled LLM records."""
    artifacts = (
        tmp_path / "config-apply-receipts-v1.json",
        tmp_path / ".feishu-self-evolution-llm.jsonl",
    )
    for path in artifacts:
        path.write_text("runtime only", encoding="utf-8")

    completed = subprocess.run(
        ["bash", str(_DOWN), "--wt", str(tmp_path)],
        cwd=tmp_path,
        env=os.environ,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert all(not path.exists() for path in artifacts)
