"""Real-process coverage for Gateway descendant ownership."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

import personal_assistant.main as main_module

from .test_e2e_up_script import _prepare_harness, _run_up
from tests.unit.personal_assistant._main_helpers import build_config


def _spawn_gateway_tree() -> tuple[subprocess.Popen[str], dict[str, int]]:
    code = """
import json
import signal
import subprocess
import sys
import time

child_code = '''import time
while True:
    time.sleep(1)
'''
same_group = subprocess.Popen([sys.executable, "-c", child_code])
detached = subprocess.Popen(
    [sys.executable, "-c", child_code], start_new_session=True
)
print(json.dumps({"same_group": same_group.pid, "detached": detached.pid}), flush=True)
while True:
    time.sleep(1)
"""
    leader = subprocess.Popen(
        [sys.executable, "-c", code],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert leader.stdout is not None
    children = json.loads(leader.stdout.readline())
    return leader, {name: int(pid) for name, pid in children.items()}


def _process_exited(pid: int) -> bool:
    snapshot = main_module.read_gateway_process_snapshot(pid)
    return snapshot is None


def _cleanup_tree(leader: subprocess.Popen[str], children: dict[str, int]) -> None:
    for pgid in {leader.pid, children["detached"]}:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        leader.wait(timeout=3)
    except subprocess.TimeoutExpired:
        leader.kill()
        leader.wait(timeout=3)


def _write_gateway_evidence(root: Path, leader_pid: int) -> None:
    config_path = (root / ".gateway-config.yaml").resolve()
    config_path.write_text("node: {}\n", encoding="utf-8")
    snapshot = main_module.read_gateway_process_snapshot(leader_pid)
    assert snapshot is not None
    (root / ".gateway.pid").write_text(str(leader_pid), encoding="utf-8")
    (root / "gateway.pid").write_text(str(leader_pid), encoding="utf-8")
    (root / "gateway.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": leader_pid,
                "process_start": snapshot.process_start,
                "config_path": str(config_path),
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
    (root / ".gateway-state.json").write_text(
        json.dumps({"pid": leader_pid, "config_path": str(config_path)}),
        encoding="utf-8",
    )
    # The Gateway-only tree fixture represents a stack whose IM already exited.
    # e2e-down requires this durable pair before it may signal any Gateway owner.
    (root / ".im.pid").write_text("999999999\n", encoding="utf-8")
    (root / ".im.identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 999999999,
                "process_start": "Mon Jul 13 12:34:56 2026",
                "cwd": str(root.resolve()),
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


def test_owned_process_snapshot_includes_same_group_and_detached_descendants() -> None:
    leader, children = _spawn_gateway_tree()
    try:
        snapshot = main_module.capture_gateway_owned_process_set(leader.pid)

        by_pid = {item.pid: item for item in snapshot.processes}
        assert set(by_pid) == {leader.pid, *children.values()}
        assert by_pid[leader.pid].pgid == leader.pid
        assert by_pid[children["same_group"]].pgid == leader.pid
        assert by_pid[children["detached"]].pgid == children["detached"]
    finally:
        _cleanup_tree(leader, children)


def test_e2e_down_reaps_same_group_and_detached_descendants(tmp_path: Path) -> None:
    leader, children = _spawn_gateway_tree()
    try:
        _write_gateway_evidence(tmp_path, leader.pid)
        repo_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["bash", str(repo_root / "scripts" / "e2e-down.sh"), "--wt", str(tmp_path)],
            cwd=repo_root,
            env={
                **os.environ,
                "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        # Surface a fail-closed teardown decision before waiting on the fixture
        # leader. Otherwise a retained leader masks the script's actual reason.
        assert result.returncode == 0, result.stderr
        leader.wait(timeout=3)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not all(
            _process_exited(pid) for pid in children.values()
        ):
            time.sleep(0.05)

        assert all(_process_exited(pid) for pid in children.values())
        assert not (tmp_path / ".gateway.pid").exists()
    finally:
        _cleanup_tree(leader, children)


def test_public_stop_reaps_same_group_and_detached_descendants(
    tmp_path: Path,
) -> None:
    leader, children = _spawn_gateway_tree()
    try:
        config = build_config(tmp_path)
        snapshot = main_module.read_gateway_process_snapshot(leader.pid)
        assert snapshot is not None
        (tmp_path / "gateway.pid").write_text(str(leader.pid), encoding="utf-8")
        (tmp_path / "gateway.identity.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pid": leader.pid,
                    "process_start": snapshot.process_start,
                    "config_path": str(config.source_path.resolve()),
                    "entry_module": "personal_assistant.main",
                    "argv": [
                        "--config",
                        str(config.source_path.resolve()),
                        "--foreground",
                    ],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / ".gateway-state.json").write_text(
            json.dumps(
                {
                    "pid": leader.pid,
                    "config_path": str(config.source_path.resolve()),
                    "log_path": str(tmp_path / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )
        result = main_module.stop_gateway(
            config_path=config.source_path,
            load_config=lambda _path: config,
        )
        leader.wait(timeout=3)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not all(
            _process_exited(pid) for pid in children.values()
        ):
            time.sleep(0.05)

        assert result.startswith(f"STOPPED pid={leader.pid}")
        assert all(_process_exited(pid) for pid in children.values())
        assert not (tmp_path / "gateway.pid").exists()
        assert not (tmp_path / ".gateway-state.json").exists()
    finally:
        _cleanup_tree(leader, children)


def test_birth_drift_fails_before_any_owned_group_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = main_module.GatewayOwnedProcessSet(
        leader_pid=2468,
        processes=(
            main_module.GatewayOwnedProcess(
                pid=2468,
                ppid=1,
                pgid=2468,
                process_start="old birth",
            ),
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_read_process_topology",
        lambda: {2468: (1, 2468)},
    )
    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: main_module.GatewayProcessSnapshot(
            pid=2468,
            process_start="new birth",
            command=None,
        ),
    )
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        main_module.os,
        "killpg",
        lambda pgid, sent_signal: signals.append((pgid, sent_signal)),
    )

    with pytest.raises(RuntimeError, match="birth"):
        main_module.signal_gateway_owned_process_set(expected, signal.SIGTERM)

    assert signals == []


def test_shell_freeze_delegates_the_complete_transaction_to_python(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    helper = repo_root / "scripts" / "e2e-owned-processes.sh"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/bash\n"
        "payload=$(cat)\n"
        "grep -q 'freeze_gateway_owned_process_set' <<<\"$payload\" || exit 42\n"
        "printf '%s\\n' '{\"leader_pid\":2468,\"processes\":[]}'\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            "ps() { printf '%s\\n' \"2468\"; }; "
            "kill() { return 0; }; "
            "export -f ps kill; "
            'e2e_freeze_gateway_owned_processes "$2" "$3" 2468 expected-birth',
            "bash",
            str(helper),
            str(repo_root / "src"),
            str(fake_python),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"leader_pid": 2468, "processes": []}


def test_e2e_up_rollback_reaps_detached_gateway_descendant(tmp_path: Path) -> None:
    env = _prepare_harness(tmp_path)
    env["NODES_STATUS"] = "offline"
    env["SPAWN_GATEWAY_DETACHED"] = "1"
    detached_pid: int | None = None
    try:
        result = _run_up(tmp_path, env)
        detached_pid = int(
            (tmp_path / "detached-gateway-child.pid").read_text(encoding="utf-8")
        )

        assert result.returncode == 1
        assert "did not become online" in result.stderr
        assert _process_exited(detached_pid)
    finally:
        if detached_pid is not None and not _process_exited(detached_pid):
            os.killpg(detached_pid, signal.SIGKILL)
