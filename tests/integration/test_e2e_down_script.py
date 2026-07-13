"""Integration coverage for identity-safe worktree e2e shutdown."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


_GATEWAY_PID = 424242
_PROCESS_START = "Mon Jul 13 12:34:56 2026"


def _write_stack_files(tmp_path: Path, *, internal_pid: int = _GATEWAY_PID) -> None:
    config_path = tmp_path / ".gateway-config.yaml"
    (tmp_path / ".gateway.pid").write_text(f"{_GATEWAY_PID}\n", encoding="utf-8")
    (tmp_path / "gateway.pid").write_text(f"{internal_pid}\n", encoding="utf-8")
    (tmp_path / ".gateway-state.json").write_text(
        json.dumps({"pid": _GATEWAY_PID}), encoding="utf-8"
    )
    (tmp_path / ".gateway-identity.json").write_text(
        json.dumps(
            {
                "pid": _GATEWAY_PID,
                "internal_pid": _GATEWAY_PID,
                "config_path": str(config_path),
                "process_start": _PROCESS_START,
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text("node: {}\n", encoding="utf-8")
    (tmp_path / ".e2e-ports.env").write_text("export IM_PORT=1\n", encoding="utf-8")
    (tmp_path / ".e2e-jwt-secret").write_text("secret\n", encoding="utf-8")
    (tmp_path / ".im.pid").write_text("434343\n", encoding="utf-8")


def _run_down(
    tmp_path: Path,
    *,
    kill_body: str,
    command: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-down.sh"
    calls_file = tmp_path / "calls.log"
    command = command or (
        f"python -m personal_assistant.main --config "
        f"{tmp_path / '.gateway-config.yaml'} --foreground --auto-bind"
    )
    shell = f"""
kill() {{
  printf 'kill %s\\n' "$*" >> "$CALLS_FILE"
  {kill_body}
}}
ps() {{
  case "$*" in
    *"command="*) printf '%s\\n' "$GATEWAY_COMMAND" ;;
    *"lstart="*) printf '%s\\n' "$PROCESS_START" ;;
    *"stat="*) printf '%s\\n' "${{PROCESS_STAT:-S}}" ;;
  esac
}}
sleep() {{
  printf 'sleep %s\\n' "$*" >> "$CALLS_FILE"
  return 0
}}
export -f kill ps sleep
exec bash "{script}" --wt "{tmp_path}"
"""
    env = dict(
        os.environ,
        CALLS_FILE=str(calls_file),
        GATEWAY_COMMAND=command,
        PROCESS_START=_PROCESS_START,
    )
    return subprocess.run(
        ["bash", "-c", shell],
        cwd=repo_root,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def test_gateway_that_survives_sigkill_fails_without_tearing_down_stack(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode != 0
    calls = (tmp_path / "calls.log").read_text(encoding="utf-8").splitlines()
    assert calls.count("sleep 0.2") == 25
    assert f"kill -9 {_GATEWAY_PID}" in calls
    assert "still appears alive" in result.stderr
    for residue in (
        ".gateway.pid",
        "gateway.pid",
        ".gateway-state.json",
        ".gateway-identity.json",
        ".im.pid",
        ".gateway-config.yaml",
        ".e2e-ports.env",
    ):
        assert (tmp_path / residue).exists(), residue
    assert "e2e stack stopped" not in result.stdout


@pytest.mark.parametrize("mismatch", ["internal_pid", "argv"])
def test_gateway_identity_mismatch_sends_no_signal_and_retains_stack(
    mismatch: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(
        tmp_path, internal_pid=999999 if mismatch == "internal_pid" else _GATEWAY_PID
    )
    command = None
    if mismatch == "argv":
        command = "python -m personal_assistant.main --config /tmp/other.yaml --foreground"

    result = _run_down(tmp_path, kill_body="return 0", command=command)

    assert result.returncode != 0
    calls_file = tmp_path / "calls.log"
    assert not calls_file.exists() or "kill " not in calls_file.read_text(
        encoding="utf-8"
    )
    assert "identity mismatch" in result.stderr
    assert (tmp_path / ".gateway.pid").exists()
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / ".im.pid").exists()


def test_confirmed_gateway_exit_cleans_lifecycle_then_stops_im(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    term_marker = tmp_path / "term-sent"
    kill_body = f"""
if [[ "$*" == "-0 {_GATEWAY_PID}" ]]; then
  [[ ! -f "{term_marker}" ]]
  return
fi
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  : > "{term_marker}"
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body, check=True)

    assert result.returncode == 0
    for residue in (
        ".gateway.pid",
        "gateway.pid",
        ".gateway-state.json",
        ".gateway-identity.json",
        ".im.pid",
        ".gateway-config.yaml",
        ".e2e-ports.env",
    ):
        assert not (tmp_path / residue).exists(), residue
    calls = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "999999" not in calls
    assert "e2e stack stopped" in result.stdout
