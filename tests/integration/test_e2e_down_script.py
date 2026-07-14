"""Integration coverage for identity-safe worktree e2e shutdown."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

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
    (tmp_path / "gateway.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": _GATEWAY_PID,
                "config_path": str(config_path),
                "process_start": _PROCESS_START,
                "entry_module": "personal_assistant.main",
                "argv": [
                    "--config",
                    str(config_path),
                    "--foreground",
                    "--auto-bind",
                ],
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text("node: {}\n", encoding="utf-8")
    (tmp_path / ".e2e-ports.env").write_text("export IM_PORT=1\n", encoding="utf-8")
    (tmp_path / ".e2e-jwt-secret").write_text("secret\n", encoding="utf-8")
    (tmp_path / ".im.pid").write_text("434343\n", encoding="utf-8")
    (tmp_path / ".im.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 434343,
                "process_start": _PROCESS_START,
                "cwd": str(tmp_path.resolve()),
                "argv": [
                    "-m",
                    "uvicorn",
                    "IM.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "1",
                ],
            }
        ),
        encoding="utf-8",
    )


def _run_down(
    tmp_path: Path,
    *,
    kill_body: str,
    command: str | None = None,
    process_stat: str | None = None,
    im_survives: bool = False,
    wt_argument: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-down.sh"
    calls_file = tmp_path / "calls.log"
    fake_bin = tmp_path / "fake-down-bin"
    fake_bin.mkdir(exist_ok=True)
    fake_ps = fake_bin / "ps"
    fake_ps.write_text(
        """#!/bin/bash
if [[ "$*" == *"-p 434343"* && "${IM_ALIVE-1}" != "1" ]]; then
  exit 1
fi
case "$*" in
  *"pid=,ppid=,pgid=,stat=,lstart="*) printf '%s 1 %s %s %s\\n' "$GATEWAY_PID" "$GATEWAY_PID" "${PROCESS_STAT-S}" "$PROCESS_START" ;;
  *"pid=,stat=,lstart="*) printf '%s %s %s\\n' "$GATEWAY_PID" "${PROCESS_STAT-S}" "$PROCESS_START" ;;
  *"pid=,ppid=,pgid="*) printf '%s 1 %s\\n' "$GATEWAY_PID" "$GATEWAY_PID" ;;
  *"pgid="*) printf '%s\\n' "$GATEWAY_PID" ;;
  *"command="*) printf '%s\\n' "$GATEWAY_COMMAND" ;;
  *"lstart="*) printf '%s\\n' "$PROCESS_START" ;;
  *"stat="*) printf '%s\\n' "${PROCESS_STAT-S}" ;;
esac
""",
        encoding="utf-8",
    )
    fake_ps.chmod(0o755)
    command = command or (
        f"python -m personal_assistant.main --config "
        f"{tmp_path / '.gateway-config.yaml'} --foreground --auto-bind"
    )
    shell = f"""
IM_ALIVE=1
export IM_ALIVE
kill() {{
  normalized=()
  for arg in "$@"; do
    [[ "$arg" == "--" ]] || normalized+=("$arg")
  done
  last_index=$(( ${{#normalized[@]}} - 1 ))
  if [[ $last_index -ge 0 && "${{normalized[$last_index]}}" =~ ^-[1-9][0-9]*$ ]]; then
    normalized[$last_index]="${{normalized[$last_index]#-}}"
  fi
  set -- "${{normalized[@]}}"
  printf 'kill %s\\n' "$*" >> "$CALLS_FILE"
  if [[ "$*" == "-0 434343" ]]; then
    [[ "$IM_ALIVE" == 1 ]]
    return
  fi
  if [[ "$*" == "434343" || "$*" == "-9 434343" ]]; then
    [[ "${{IM_SURVIVES-0}}" == 1 ]] || IM_ALIVE=0
    return 0
  fi
  {kill_body}
}}
sleep() {{
  printf 'sleep %s\\n' "$*" >> "$CALLS_FILE"
  return 0
}}
export -f kill sleep
exec bash "{script}" --wt "{wt_argument or tmp_path}"
"""
    env = dict(
        os.environ,
        CALLS_FILE=str(calls_file),
        GATEWAY_COMMAND=command,
        GATEWAY_PID=str(_GATEWAY_PID),
        PATH=f"{fake_bin}:{os.environ['PATH']}",
        PROCESS_START=_PROCESS_START,
        REAL_PYTHON=sys.executable,
        E2E_WT=str(tmp_path),
        IM_SURVIVES="1" if im_survives else "0",
    )
    if process_stat is not None:
        env["PROCESS_STAT"] = process_stat
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
        "gateway.identity.json",
        ".im.pid",
        ".gateway-config.yaml",
        ".e2e-ports.env",
    ):
        assert (tmp_path / residue).exists(), residue
    assert "e2e stack stopped" not in result.stdout


@pytest.mark.parametrize("mismatch", ["internal_pid", "persisted_argv"])
def test_gateway_identity_mismatch_sends_no_signal_and_retains_stack(
    mismatch: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(
        tmp_path, internal_pid=999999 if mismatch == "internal_pid" else _GATEWAY_PID
    )
    if mismatch == "persisted_argv":
        identity_path = tmp_path / "gateway.identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["argv"][1] = "/tmp/other.yaml"
        identity_path.write_text(json.dumps(identity), encoding="utf-8")

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode != 0
    calls_file = tmp_path / "calls.log"
    assert not calls_file.exists() or "kill " not in calls_file.read_text(
        encoding="utf-8"
    )
    assert "identity mismatch" in result.stderr
    assert (tmp_path / ".gateway.pid").exists()
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / ".im.pid").exists()


def test_live_command_rendering_is_audit_only_when_instance_matches(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    (tmp_path / ".gateway-config.yaml.lock").write_text("", encoding="utf-8")
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

    result = _run_down(
        tmp_path,
        kill_body=kill_body,
        command="rendering deliberately differs from persisted audit metadata",
        check=True,
    )

    assert result.returncode == 0
    for residue in (
        ".gateway.pid",
        "gateway.pid",
        ".gateway-state.json",
        "gateway.identity.json",
        ".im.pid",
        ".gateway-config.yaml",
        ".gateway-config.yaml.lock",
        ".e2e-ports.env",
    ):
        assert not (tmp_path / residue).exists(), residue
    calls_path = tmp_path / "calls.log"
    calls = calls_path.read_text(encoding="utf-8") if calls_path.exists() else ""
    assert "999999" not in calls
    assert "e2e stack stopped" in result.stdout


def test_zombie_gateway_is_exit_confirmed_without_signalling_its_pid(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)

    result = _run_down(
        tmp_path,
        kill_body="return 0",
        process_stat="Z",
        check=True,
    )

    calls_path = tmp_path / "calls.log"
    calls = calls_path.read_text(encoding="utf-8") if calls_path.exists() else ""
    assert str(_GATEWAY_PID) not in calls
    assert not (tmp_path / ".gateway.pid").exists()
    assert "e2e stack stopped" in result.stdout


def test_signal_permission_failure_retains_stack_and_reports_failure(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  return 1
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body)

    assert result.returncode != 0
    assert "cannot be signalled" in result.stderr
    assert (tmp_path / ".gateway.pid").exists()
    assert (tmp_path / ".im.pid").exists()


def test_worktree_symlink_alias_resolves_to_same_config_identity(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    wt_alias = tmp_path.parent / f"{tmp_path.name}-alias"
    wt_alias.symlink_to(tmp_path, target_is_directory=True)
    term_marker = tmp_path / "term-sent"
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  : > "{term_marker}"
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(
        tmp_path,
        kill_body=kill_body,
        wt_argument=wt_alias,
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".gateway.pid").exists()


@pytest.mark.parametrize(
    "internal_evidence",
    ["gateway.pid", "gateway.identity.json", ".gateway-state.json"],
)
def test_missing_external_pid_with_internal_evidence_fails_before_any_signal(
    internal_evidence: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    (tmp_path / ".gateway.pid").unlink()
    for evidence in ("gateway.pid", "gateway.identity.json", ".gateway-state.json"):
        if evidence != internal_evidence:
            (tmp_path / evidence).unlink()

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode == 1
    calls_path = tmp_path / "calls.log"
    assert not calls_path.exists() or "kill " not in calls_path.read_text(
        encoding="utf-8"
    )
    assert "Gateway lifecycle evidence" in result.stderr
    assert (tmp_path / internal_evidence).exists()
    assert (tmp_path / ".im.pid").exists()


def test_nonregular_external_pid_with_internal_evidence_fails_before_any_signal(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    (tmp_path / ".gateway.pid").unlink()
    (tmp_path / ".gateway.pid").mkdir()

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode == 1
    calls_path = tmp_path / "calls.log"
    assert not calls_path.exists() or "kill " not in calls_path.read_text(
        encoding="utf-8"
    )
    assert "regular external PID" in result.stderr
    assert (tmp_path / ".gateway.pid").is_dir()
    assert (tmp_path / ".im.pid").exists()


def test_dangling_external_pid_symlink_retains_whole_stack(tmp_path: Path) -> None:
    _write_stack_files(tmp_path)
    (tmp_path / ".gateway.pid").unlink()
    (tmp_path / ".gateway.pid").symlink_to(tmp_path / "missing-external-pid")

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode == 1
    calls_path = tmp_path / "calls.log"
    assert not calls_path.exists() or "kill " not in calls_path.read_text(
        encoding="utf-8"
    )
    assert (tmp_path / ".gateway.pid").is_symlink()
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / ".im.pid").exists()
    assert (tmp_path / ".gateway-config.yaml").exists()


@pytest.mark.parametrize(
    "internal_evidence",
    ["gateway.pid", "gateway.identity.json", ".gateway-state.json"],
)
def test_dangling_internal_evidence_without_external_owner_retains_stack(
    internal_evidence: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    (tmp_path / ".gateway.pid").unlink()
    for evidence in ("gateway.pid", "gateway.identity.json", ".gateway-state.json"):
        path = tmp_path / evidence
        path.unlink()
        if evidence == internal_evidence:
            path.symlink_to(tmp_path / f"missing-{evidence}")

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode == 1
    calls_path = tmp_path / "calls.log"
    assert not calls_path.exists() or "kill " not in calls_path.read_text(
        encoding="utf-8"
    )
    assert (tmp_path / internal_evidence).is_symlink()
    assert (tmp_path / ".im.pid").exists()


@pytest.mark.parametrize("state_mode", ["malformed", "different_pid"])
def test_invalid_state_evidence_is_never_partially_deleted(
    state_mode: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        "{" if state_mode == "malformed" else json.dumps({"pid": 999999}),
        encoding="utf-8",
    )

    result = _run_down(tmp_path, kill_body="return 0")

    assert result.returncode == 1
    for evidence in (
        ".gateway.pid",
        "gateway.pid",
        "gateway.identity.json",
        ".gateway-state.json",
        ".im.pid",
        ".gateway-config.yaml",
    ):
        assert (tmp_path / evidence).exists(), evidence


def test_same_pid_new_birth_before_cleanup_causes_zero_deletion(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  "$REAL_PYTHON" - "$E2E_WT/gateway.identity.json" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["process_start"] = "Tue Jul 14 12:34:56 2026"
path.write_text(json.dumps(payload), encoding="utf-8")
PY
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body)

    assert result.returncode == 1
    assert "evidence changed during cleanup" in result.stderr
    for evidence in (
        ".gateway.pid",
        "gateway.pid",
        "gateway.identity.json",
        ".gateway-state.json",
        ".im.pid",
        ".gateway-config.yaml",
    ):
        assert (tmp_path / evidence).exists(), evidence


def test_same_content_inode_drift_before_cleanup_causes_zero_deletion(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  cp "$E2E_WT/.gateway-state.json" "$E2E_WT/.gateway-state.json.replacement"
  mv "$E2E_WT/.gateway-state.json.replacement" "$E2E_WT/.gateway-state.json"
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body)

    assert result.returncode == 1
    for evidence in (
        ".gateway.pid",
        "gateway.pid",
        "gateway.identity.json",
        ".gateway-state.json",
        ".im.pid",
        ".gateway-config.yaml",
    ):
        assert (tmp_path / evidence).exists(), evidence


def test_runtime_owned_internal_evidence_may_self_clear_on_exit(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  rm -f "$E2E_WT/gateway.pid"
  rm -f "$E2E_WT/gateway.identity.json"
  rm -f "$E2E_WT/.gateway-state.json"
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".gateway.pid").exists()
    assert not (tmp_path / ".im.pid").exists()
    assert not (tmp_path / ".gateway-config.yaml").exists()


def test_all_gateway_evidence_absent_allows_im_stop(tmp_path: Path) -> None:
    (tmp_path / ".im.pid").write_text("434343\n", encoding="utf-8")
    (tmp_path / ".im.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 434343,
                "process_start": _PROCESS_START,
                "cwd": str(tmp_path.resolve()),
                "argv": [
                    "-m",
                    "uvicorn",
                    "IM.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "1",
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _run_down(tmp_path, kill_body="return 0", check=True)

    assert result.returncode == 0
    calls = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "kill 434343" in calls
    assert not (tmp_path / ".im.pid").exists()
    assert not (tmp_path / ".im.identity.json").exists()


def test_im_birth_mismatch_sends_no_signal_and_retains_evidence(tmp_path: Path) -> None:
    _write_stack_files(tmp_path)
    identity_path = tmp_path / ".im.identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["process_start"] = "Sun Jul 12 00:00:00 2026"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")

    result = _run_down(tmp_path, kill_body="return 0")

    calls_path = tmp_path / "calls.log"
    calls = calls_path.read_text(encoding="utf-8") if calls_path.exists() else ""
    assert result.returncode == 1
    assert "kill 434343" not in calls
    assert "IM process identity mismatch" in result.stderr
    assert (tmp_path / ".im.pid").exists()
    assert identity_path.exists()


def test_im_survivor_retains_config_and_sidecar(tmp_path: Path) -> None:
    (tmp_path / ".im.pid").write_text("434343\n", encoding="utf-8")
    (tmp_path / ".im.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 434343,
                "process_start": _PROCESS_START,
                "cwd": str(tmp_path.resolve()),
                "argv": [
                    "-m",
                    "uvicorn",
                    "IM.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "1",
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / ".gateway-config.yaml").write_text("node: {}\n", encoding="utf-8")
    (tmp_path / ".gateway-config.yaml.lock").write_text("", encoding="utf-8")

    result = _run_down(
        tmp_path,
        kill_body="return 0",
        im_survives=True,
    )

    assert result.returncode == 1
    assert "IM pid=434343 still appears alive" in result.stderr
    assert (tmp_path / ".im.pid").exists()
    assert (tmp_path / ".gateway-config.yaml").exists()
    assert (tmp_path / ".gateway-config.yaml.lock").exists()


def test_busy_config_sidecar_is_not_unlinked_after_service_exit(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    lock_path = tmp_path / ".gateway-config.yaml.lock"
    lock_path.write_text("", encoding="utf-8")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl,sys,time; "
            "f=open(sys.argv[1], 'r+'); "
            "fcntl.flock(f, fcntl.LOCK_EX); "
            "print('ready', flush=True); time.sleep(30)",
            str(lock_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "ready"
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  export PROCESS_STAT=""
fi
return 0
"""

    try:
        result = _run_down(tmp_path, kill_body=kill_body)

        assert result.returncode == 1
        assert "config lock is busy" in result.stderr
        assert lock_path.exists()
        assert (tmp_path / ".gateway-config.yaml").exists()
    finally:
        holder.terminate()
        holder.wait(timeout=3)
