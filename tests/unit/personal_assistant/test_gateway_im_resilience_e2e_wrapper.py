"""Focused tests for the bugfix-446 resilience e2e wrapper and script prep path."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from shutil import which

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

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:  # noqa: ARG002
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

    def _fake_killpg(pgid: int, sig: signal.Signals | int) -> None:
        killed.append((pgid, signal.Signals(sig)))

    monkeypatch.setattr(wrapper.os, "killpg", _fake_killpg)

    with pytest.raises(AssertionError, match="timed out"):
        wrapper._run_resilience_script(  # noqa: SLF001
            ["bash", "scripts/e2e-resilience.sh"],
            cwd=tmp_path,
            timeout=0.01,
        )

    assert popen_kwargs["start_new_session"] is True
    assert killed == [
        (43210, signal.SIGTERM),
        (43210, signal.SIGKILL),
    ]


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


def test_e2e_up_script_yq_path_sets_each_agent_workspace_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The yq config path must derive each workspace_root from its own agent id."""

    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "e2e-up.sh"
    yq_path = which("yq")
    if yq_path is None:
        script_text = script.read_text()
        assert (
            '.agents[].workspace_root = "$WORKSPACE_DIR/" + .agents[].agent_id'
            not in script_text
        )
        assert ".agents |= map(" in script_text
        return

    main_config = tmp_path / "config.yaml"
    main_config.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: main-node",
                "agents:",
                "  - agent_id: alpha",
                "    workspace_root: /old/alpha",
                "  - agent_id: beta",
                "    workspace_root: /old/beta",
                "channels:",
                "  - name: web_relay",
                "    enabled: true",
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
    (bin_dir / "python").symlink_to(sys.executable)
    (bin_dir / "python3").symlink_to(sys.executable)
    (bin_dir / "yq").symlink_to(yq_path)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")

    try:
        result = subprocess.run(
            [
                "/bin/bash",
                str(script),
                "--wt",
                str(tmp_path),
                "--main-config",
                str(main_config),
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        mutated = yaml.safe_load((tmp_path / ".gateway-config.yaml").read_text())
        workspace_dir = Path(tmp_path / ".gateway-workspace")
        assert [agent["workspace_root"] for agent in mutated["agents"]] == [
            str(workspace_dir / "alpha"),
            str(workspace_dir / "beta"),
        ]
        assert (workspace_dir / "alpha").is_dir()
        assert (workspace_dir / "beta").is_dir()
    finally:
        subprocess.run(
            ["/bin/bash", str(repo_root / "scripts" / "e2e-down.sh"), "--wt", str(tmp_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
