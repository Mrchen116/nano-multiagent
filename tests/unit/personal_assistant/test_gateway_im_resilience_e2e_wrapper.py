"""Focused tests for the bugfix-446 resilience e2e wrapper and script prep path."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.e2e.critical_paths import test_gateway_im_resilience_critical_path as wrapper


def test_resilience_wrapper_kills_process_group_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A timeout must kill the whole bash process group, not just the bash parent."""

    popen_kwargs: dict[str, object] = {}
    killed: list[tuple[int, signal.Signals]] = []

    class _TimedOutProcess:
        pid = 43210

        def communicate(
            self, timeout: float | None = None
        ) -> tuple[str, str]:  # noqa: ARG002
            raise subprocess.TimeoutExpired(
                cmd=("bash", "scripts/e2e-resilience.sh"),
                timeout=timeout,
                output="partial stdout",
                stderr="partial stderr",
            )

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return -signal.SIGTERM

    def _fake_popen(*_args, **kwargs):
        popen_kwargs.update(kwargs)
        return _TimedOutProcess()

    monkeypatch.setattr(wrapper.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(wrapper.os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))

    with pytest.raises(AssertionError, match="timed out"):
        wrapper._run_resilience_script(  # noqa: SLF001
            ["bash", "scripts/e2e-resilience.sh"],
            cwd=tmp_path,
            timeout=0.01,
        )

    assert popen_kwargs["start_new_session"] is True
    assert killed == [(43210, signal.SIGTERM)]


def test_resilience_script_prepare_only_works_without_yq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The script must mutate the isolated config with its Python fallback when yq is absent."""

    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "e2e-resilience.sh"
    main_config = tmp_path / "config.yaml"
    main_config.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: main-node",
                "agents:",
                "  - agent_id: default-agent",
                "    workspace_root: /old/default-agent",
                "channels: []",
                "im_service:",
                "  url: http://old-im",
                "  username: nano",
                "  password: nano1234",
                "llm:",
                "  default_model: kimiCoding:K2.6",
                "  providers:",
                "    - name: anthropic",
                "      base_url: http://127.0.0.1:4000",
                "      models:",
                "        - name: kimiCoding:K2.6",
                "",
            ]
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    if shutil_yq := __import__("shutil").which("yq"):
        pytest.skip(f"controlled PATH still finds yq at {shutil_yq}")

    result = subprocess.run(
        [
            "/bin/bash",
            str(script),
            "--prepare-only",
            "--wt",
            str(tmp_path),
            "--main-config",
            str(main_config),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    mutated = yaml.safe_load((tmp_path / ".gateway-config.yaml").read_text())
    workspace_dir = str(tmp_path / ".gateway-workspace")
    assert mutated["node"]["node_id"].startswith("wt-resilience-")
    assert mutated["node"]["workspace_base"] == workspace_dir
    assert mutated["im_service"]["url"].startswith("http://127.0.0.1:")
    assert mutated["agents"][0]["workspace_root"] == str(
        Path(workspace_dir) / "default-agent"
    )
    assert (Path(workspace_dir) / "default-agent").is_dir()
