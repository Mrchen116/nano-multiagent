"""Integration coverage for fail-atomic worktree e2e startup."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


_PROCESS_START = "Mon Jul 13 12:34:56 2026"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_harness(tmp_path: Path, *, startup_timeout: float = 10) -> dict[str, str]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    ticks_path = tmp_path / "sleep-ticks"
    ticks_path.write_text("0", encoding="utf-8")
    config_path = tmp_path / "main-config.yaml"
    workspace = tmp_path / "main-workspace"
    workspace.mkdir()
    config_path.write_text(
        f"""\
node:
  node_id: source-node
agents:
  - agent_id: default-agent
    workspace_root: {workspace}
channels: []
gateway:
  startup_timeout_seconds: {startup_timeout}
  shutdown_grace_seconds: 1
  poll_interval_seconds: 0.1
im_service:
  url: http://127.0.0.1:8011
  username: nano
  password: nano1234
llm:
  default_model: anthropic:test-model
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: anthropic:test-model
""",
        encoding="utf-8",
    )
    _write_executable(
        fake_bin / "sleep",
        """#!/bin/bash
ticks=$(cat "$E2E_TICKS_FILE")
printf '%s\n' "$((ticks + 1))" > "$E2E_TICKS_FILE"
/bin/sleep 0.002
""",
    )
    _write_executable(
        fake_bin / "curl",
        """#!/bin/bash
case "$*" in
  *"/im/v1/auth/login"*)
    printf '%s\n' '{"user":{"id":"user-e2e"},"access_token":"token-e2e"}'
    ;;
  *"/im/v1/nodes"*)
    node_id="$($REAL_PYTHON - "$E2E_WT/.gateway-config.yaml" <<'PY'
import sys, yaml
print(yaml.safe_load(open(sys.argv[1]))["node"]["node_id"])
PY
)"
    printf '[{"node_id":"%s","status":"online"}]\n' "$node_id"
    ;;
  *) printf '%s\n' '{}' ;;
esac
""",
    )
    _write_executable(
        fake_bin / "python",
        """#!/bin/bash
set -e
if [[ "${1-}" == "-m" && "${2-}" == "uvicorn" ]]; then
  trap 'exit 0' TERM INT
  while true; do /bin/sleep 1; done
fi
if [[ "${1-}" == "-m" && "${2-}" == "personal_assistant.main" ]]; then
  config_path=""
  args=("${@:3}")
  for ((index=0; index<${#args[@]}; index++)); do
    if [[ "${args[$index]}" == "--config" ]]; then
      config_path="${args[$((index + 1))]}"
    fi
  done
  if [[ "${EXPECT_STALE_CLEAN-0}" == "1" ]] \
    && [[ -e "$E2E_WT/gateway.pid" || -e "$E2E_WT/gateway.identity.json" \
      || -e "$E2E_WT/.gateway-state.json" ]]; then
    printf '%s\n' stale-evidence-visible > "$E2E_WT/spawn-check"
    exit 41
  fi
  if [[ "${GATEWAY_IDENTITY_MODE-ready}" != "timeout" ]]; then
    target_ticks="${IDENTITY_AFTER_TICKS-0}"
    while [[ "$(cat "$E2E_TICKS_FILE")" -lt "$target_ticks" ]]; do
      /bin/sleep 0.001
    done
    "$REAL_PYTHON" - "$config_path" "$$" "${args[@]}" <<'PY'
import json
from pathlib import Path
import sys

config_path = Path(sys.argv[1]).resolve()
pid = int(sys.argv[2])
argv = sys.argv[3:]
root = config_path.parent
(root / "gateway.pid").write_text(str(pid), encoding="utf-8")
(root / "gateway.identity.json").write_text(
    json.dumps(
        {
            "schema_version": 1,
            "pid": pid,
            "process_start": "Mon Jul 13 12:34:56 2026",
            "config_path": str(config_path),
            "entry_module": "personal_assistant.main",
            "argv": argv,
        }
    ),
    encoding="utf-8",
)
PY
  fi
  trap 'exit 0' TERM INT
  while true; do /bin/sleep 1; done
fi
exec "$REAL_PYTHON" "$@"
""",
    )
    return {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "REAL_PYTHON": sys.executable,
        "E2E_TICKS_FILE": str(ticks_path),
        "E2E_WT": str(tmp_path),
        "PROCESS_START": _PROCESS_START,
        "MAIN_CONFIG": str(config_path),
    }


def _run_up(
    tmp_path: Path,
    env: dict[str, str],
    *,
    default_from: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-up.sh"
    if default_from is None:
        argv = [
            "bash",
            str(script),
            "--wt",
            str(tmp_path),
            "--main-config",
            env["MAIN_CONFIG"],
        ]
        cwd = repo_root
    else:
        argv = [
            "bash",
            "-c",
            f'cd -L "{default_from}" && exec bash "{script}" '
            f'--main-config "{env["MAIN_CONFIG"]}"',
        ]
        cwd = default_from.parent
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def _owned_pids(tmp_path: Path) -> list[int]:
    pids: list[int] = []
    for name in (".gateway.pid", ".im.pid"):
        try:
            pids.append(int((tmp_path / name).read_text(encoding="utf-8").strip()))
        except (FileNotFoundError, ValueError):
            pass
    return pids


def _cleanup_owned(tmp_path: Path) -> None:
    for pid in _owned_pids(tmp_path):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_delayed_runtime_identity_uses_configured_startup_budget(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path, startup_timeout=10)
    env["IDENTITY_AFTER_TICKS"] = "70"

    try:
        result = _run_up(tmp_path, env)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "gateway.identity.json").exists()
        assert int(env["IDENTITY_AFTER_TICKS"]) > 60
    finally:
        _cleanup_owned(tmp_path)


def test_identity_timeout_rolls_back_exact_spawned_stack_and_preserves_logs(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path, startup_timeout=0.5)
    env["GATEWAY_IDENTITY_MODE"] = "timeout"

    try:
        result = _run_up(tmp_path, env)
        spawned_pids = _owned_pids(tmp_path)

        assert result.returncode == 1
        assert spawned_pids
        assert all(not _pid_alive(pid) for pid in spawned_pids)
        assert not (tmp_path / ".gateway.pid").exists()
        assert not (tmp_path / ".im.pid").exists()
        assert not (tmp_path / "gateway.pid").exists()
        assert not (tmp_path / "gateway.identity.json").exists()
        assert (tmp_path / ".gateway.log").exists()
        assert (tmp_path / ".im.log").exists()
    finally:
        _cleanup_owned(tmp_path)


def test_preflight_clears_stale_internal_evidence_without_signalling_its_pid(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    sentinel = subprocess.Popen(["/bin/sleep", "30"])
    (tmp_path / "gateway.pid").write_text(str(sentinel.pid), encoding="utf-8")
    (tmp_path / "gateway.identity.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gateway-state.json").write_text("{}", encoding="utf-8")
    env["EXPECT_STALE_CLEAN"] = "1"

    try:
        result = _run_up(tmp_path, env)

        assert result.returncode == 0, result.stderr
        assert sentinel.poll() is None
        assert not (tmp_path / "spawn-check").exists()
    finally:
        _cleanup_owned(tmp_path)
        sentinel.terminate()
        sentinel.wait(timeout=3)


def test_default_symlink_cwd_is_canonicalized_after_argument_parsing(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    alias = tmp_path.parent / f"{tmp_path.name}-alias"
    alias.symlink_to(tmp_path, target_is_directory=True)

    try:
        result = _run_up(tmp_path, env, default_from=alias)

        assert result.returncode == 0, result.stderr
        assert f"e2e stack ready in {tmp_path.resolve()}" in result.stdout.splitlines()
        identity = json.loads(
            (tmp_path / "gateway.identity.json").read_text(encoding="utf-8")
        )
        assert identity["config_path"] == str(
            (tmp_path / ".gateway-config.yaml").resolve()
        )
    finally:
        _cleanup_owned(tmp_path)
