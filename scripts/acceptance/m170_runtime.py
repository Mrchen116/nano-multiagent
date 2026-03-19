"""Rebuild and start the canonical M170 acceptance runtime from a clean local state."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

def _resolve_canonical_repo_root(script_path: Path) -> Path:
    """Resolve the main repository root even when this script runs from a worktree.

    Args:
        script_path: Absolute path to this runtime management script.

    Returns:
        Main checkout root that owns the shared canonical acceptance runtime.
    """

    resolved = script_path.expanduser().resolve()
    parts = resolved.parts
    if ".worktrees" in parts:
        worktrees_index = parts.index(".worktrees")
        return Path(*parts[:worktrees_index])
    return resolved.parents[2]


CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_REPO_ROOT = _resolve_canonical_repo_root(Path(__file__).resolve())
SRC_ROOT = CHECKOUT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import AgentProfileRepository
from personal_assistant.main import stop_gateway

REPO_ROOT = CHECKOUT_ROOT
RUNTIME_ROOT = CANONICAL_REPO_ROOT / "ACCEPTANCE" / "m170-runtime"
RUNTIME_DB = RUNTIME_ROOT / "im_service.sqlite3"
RUNTIME_CONFIG = RUNTIME_ROOT / "node-config.yaml"
RUNTIME_IM_LOG = RUNTIME_ROOT / "im.log"
RUNTIME_GATEWAY_LOG = RUNTIME_ROOT / "gateway.log"
RUNTIME_HEARTBEAT_STATE = RUNTIME_ROOT / "heartbeat-state.json"
RUNTIME_GATEWAY_STATE = RUNTIME_ROOT / ".gateway-state.json"
RUNTIME_UPLOADS = RUNTIME_ROOT / "uploads"
RUNTIME_WORKSPACE = RUNTIME_ROOT / "workspace"
IM_PORT = 18031
KERNEL_PORT = 18070
IM_BASE_URL = f"http://127.0.0.1:{IM_PORT}"
IM_HEALTH_URL = f"{IM_BASE_URL}/chat"
IM_NODES_URL = f"{IM_BASE_URL}/im/v1/nodes"
GATEWAY_HEALTH_URL = f"http://127.0.0.1:{KERNEL_PORT}/v1/health"
DEFAULT_READY_TIMEOUT_SECONDS = 20.0
DEFAULT_STOP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    runtime_root: str
    runtime_db: str
    config_path: str
    im_log: str
    gateway_log: str
    im_url: str
    gateway_health_url: str
    im_http_ok: bool
    gateway_http_ok: bool
    node_online: bool
    node_status: str | None


@dataclass(frozen=True, slots=True)
class CanonicalRuntimeAgent:
    agent_id: str
    title: str
    display_name: str
    system_prompt: str

    @property
    def workspace_root(self) -> Path:
        return (RUNTIME_WORKSPACE / self.agent_id).resolve()


CANONICAL_RUNTIME_AGENTS: tuple[CanonicalRuntimeAgent, ...] = (
    CanonicalRuntimeAgent(
        agent_id="assistant",
        title="My Assistant",
        display_name="assistant",
        system_prompt="You are assistant.",
    ),
    CanonicalRuntimeAgent(
        agent_id="agent-m170-alpha",
        title="Agent M170 Alpha",
        display_name="Agent M170 Alpha",
        system_prompt="Reply exactly with ALPHA_ACK_M170.",
    ),
    CanonicalRuntimeAgent(
        agent_id="agent-m170-beta",
        title="Agent M170 Beta",
        display_name="Agent M170 Beta",
        system_prompt="Reply exactly with BETA_ACK_M170.",
    ),
)


def _wait_for_url(url: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        try:
            response = httpx.get(url, timeout=1.0, trust_env=False)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _wait_for_gateway_health(url: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        try:
            response = httpx.get(url, timeout=1.0, trust_env=False)
            payload = response.json()
            if response.status_code == 200 and isinstance(payload, dict) and bool(payload.get("healthy")):
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _ensure_runtime_layout() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_UPLOADS.mkdir(parents=True, exist_ok=True)
    RUNTIME_WORKSPACE.mkdir(parents=True, exist_ok=True)
    for agent in CANONICAL_RUNTIME_AGENTS:
        agent.workspace_root.mkdir(parents=True, exist_ok=True)


def _write_runtime_config() -> None:
    payload = {
        "node": {"node_id": "m170-node"},
        "agents": [
            {
                "agent_id": agent.agent_id,
                "title": agent.title,
                "workspace_root": str(agent.workspace_root),
            }
            for agent in CANONICAL_RUNTIME_AGENTS
        ],
        "channels": [{"name": "web_relay", "enabled": True}],
        "kernel": {
            "command": (
                f"python -m uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port {KERNEL_PORT}"
            )
        },
        "im_service": {"url": IM_BASE_URL},
    }
    _write_yaml(RUNTIME_CONFIG, payload)


def _initialize_runtime_db() -> None:
    connection = connect(RUNTIME_DB)
    try:
        initialize_schema(connection)
        profiles = AgentProfileRepository(connection)
        for agent in CANONICAL_RUNTIME_AGENTS:
            profiles.upsert_profile(
                agent_id=agent.agent_id,
                owner_id="",
                display_name=agent.display_name,
                description="Runtime agent advertised by m170-node.",
                system_prompt=agent.system_prompt,
                skills=[],
                tool_allowlist=[],
                group_reply_policy="MENTION",
                default_model=None,
                workspace_root=str(agent.workspace_root),
            )
        connection.commit()
    finally:
        connection.close()


def _list_gateway_pids_for_config(config_path: Path) -> set[int]:
    try:
        completed = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except Exception:
        return set()
    needle = f"--config {config_path}"
    pids: set[int] = set()
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or needle not in line or "personal_assistant.main" not in line:
            continue
        pid_text, _, _command = line.partition(" ")
        try:
            pids.add(int(pid_text))
        except ValueError:
            continue
    return pids



def _list_listener_pids(port: int) -> set[int]:
    try:
        completed = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return set()
    pids: set[int] = set()
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            pids.add(int(line))
        except ValueError:
            continue
    return pids



def _terminate_pid(pid: int, *, timeout_seconds: float) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.25)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return



def stop_runtime(*, timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> dict[str, str]:
    result: dict[str, str] = {}
    if RUNTIME_CONFIG.exists():
        try:
            result["gateway"] = stop_gateway(config_path=RUNTIME_CONFIG)
        except ValueError as exc:
            result["gateway"] = f"STALE CONFIG config={RUNTIME_CONFIG} detail={exc}"
    else:
        result["gateway"] = f"NOT CONFIGURED config={RUNTIME_CONFIG}"
    state_pid = None
    if RUNTIME_GATEWAY_STATE.is_file():
        try:
            payload = json.loads(RUNTIME_GATEWAY_STATE.read_text(encoding="utf-8"))
            state_pid = int(payload.get("pid"))
        except Exception:
            state_pid = None
    if state_pid is not None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() <= deadline:
            try:
                os.kill(state_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.25)
    im_pid = None
    im_pid_path = RUNTIME_ROOT / ".im-state.json"
    if im_pid_path.is_file():
        try:
            payload = json.loads(im_pid_path.read_text(encoding="utf-8"))
            im_pid = int(payload["pid"])
            os.kill(im_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            pass
        finally:
            im_pid_path.unlink(missing_ok=True)
    stale_pids = _list_gateway_pids_for_config(RUNTIME_CONFIG) | _list_listener_pids(KERNEL_PORT)
    stale_pids.discard(os.getpid())
    if state_pid is not None:
        stale_pids.discard(state_pid)
    if im_pid is not None:
        stale_pids.discard(im_pid)
    for pid in sorted(stale_pids):
        _terminate_pid(pid, timeout_seconds=timeout_seconds)
    result["im_url_stopped"] = "true" if not _wait_for_url(IM_HEALTH_URL, timeout_seconds=1.0) else "false"
    return result


def rebuild_runtime() -> dict[str, str]:
    stop_runtime()
    if RUNTIME_DB.exists():
        RUNTIME_DB.unlink()
    for path in (RUNTIME_IM_LOG, RUNTIME_GATEWAY_LOG, RUNTIME_HEARTBEAT_STATE, RUNTIME_GATEWAY_STATE):
        path.unlink(missing_ok=True)
    if RUNTIME_UPLOADS.exists():
        shutil.rmtree(RUNTIME_UPLOADS)
    if RUNTIME_WORKSPACE.exists():
        shutil.rmtree(RUNTIME_WORKSPACE)
    _ensure_runtime_layout()
    _write_runtime_config()
    _initialize_runtime_db()
    return {
        "runtime_root": str(RUNTIME_ROOT),
        "runtime_db": str(RUNTIME_DB),
        "config_path": str(RUNTIME_CONFIG),
        "status": "rebuilt",
    }


def _spawn_im() -> int:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing_pythonpath else f"{SRC_ROOT}{os.pathsep}{existing_pythonpath}"
    env["IM_DB_PATH"] = str(RUNTIME_DB)
    env["IM_UPLOAD_DIR"] = str(RUNTIME_UPLOADS)
    log_handle = RUNTIME_IM_LOG.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "IM.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(IM_PORT),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (RUNTIME_ROOT / ".im-state.json").write_text(json.dumps({"pid": process.pid}, indent=2), encoding="utf-8")
    return process.pid


def _start_gateway() -> str:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing_pythonpath else f"{SRC_ROOT}{os.pathsep}{existing_pythonpath}"
    completed = subprocess.run(
        [sys.executable, "-m", "personal_assistant.main", "--config", str(RUNTIME_CONFIG)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "gateway start failed")
    return completed.stdout.strip()


def _wait_for_node_online(*, timeout_seconds: float) -> RuntimeStatus:
    deadline = time.monotonic() + timeout_seconds
    last_status = runtime_status()
    while time.monotonic() <= deadline:
        last_status = runtime_status()
        if last_status.node_online:
            return last_status
        time.sleep(0.25)
    return last_status


def start_runtime(*, timeout_seconds: float = DEFAULT_READY_TIMEOUT_SECONDS) -> dict[str, str]:
    rebuild_runtime()
    im_pid = _spawn_im()
    if not _wait_for_url(IM_HEALTH_URL, timeout_seconds=timeout_seconds):
        raise RuntimeError(f"IM did not become ready on {IM_HEALTH_URL}; pid={im_pid}")
    gateway_started = _start_gateway()
    if not _wait_for_gateway_health(GATEWAY_HEALTH_URL, timeout_seconds=timeout_seconds):
        raise RuntimeError(f"Gateway did not become healthy on {GATEWAY_HEALTH_URL}")
    status = _wait_for_node_online(timeout_seconds=timeout_seconds)
    result = {
        "im_pid": str(im_pid),
        "gateway": gateway_started,
        "node_online": str(status.node_online).lower(),
        "node_status": status.node_status or "",
    }
    if not status.node_online:
        raise RuntimeError(f"Gateway became healthy but node m170-node is not online: {json.dumps(result, ensure_ascii=False)}")
    return result


def runtime_status() -> RuntimeStatus:
    im_http_ok = False
    gateway_http_ok = False
    node_online = False
    node_status = None
    try:
        response = httpx.get(IM_HEALTH_URL, timeout=1.0, trust_env=False)
        im_http_ok = response.status_code == 200
    except Exception:
        im_http_ok = False
    try:
        response = httpx.get(GATEWAY_HEALTH_URL, timeout=1.0, trust_env=False)
        payload = response.json()
        gateway_http_ok = response.status_code == 200 and isinstance(payload, dict) and bool(payload.get("healthy"))
    except Exception:
        gateway_http_ok = False
    try:
        response = httpx.get(IM_NODES_URL, timeout=1.0, trust_env=False)
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict) and item.get("node_id") == "m170-node":
                        node_status = str(item.get("status")) if item.get("status") is not None else None
                        node_online = node_status == "online"
                        break
    except Exception:
        node_online = False
    return RuntimeStatus(
        runtime_root=str(RUNTIME_ROOT),
        runtime_db=str(RUNTIME_DB),
        config_path=str(RUNTIME_CONFIG),
        im_log=str(RUNTIME_IM_LOG),
        gateway_log=str(RUNTIME_GATEWAY_LOG),
        im_url=IM_HEALTH_URL,
        gateway_health_url=GATEWAY_HEALTH_URL,
        im_http_ok=im_http_ok,
        gateway_http_ok=gateway_http_ok,
        node_online=node_online,
        node_status=node_status,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the canonical M170 acceptance runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("rebuild", help="Recreate the runtime directory state from scratch")
    subparsers.add_parser("start", help="Rebuild the runtime and start IM plus gateway")
    subparsers.add_parser("stop", help="Stop the runtime processes tracked under the canonical runtime root")
    subparsers.add_parser("status", help="Show current runtime readiness")
    args = parser.parse_args(argv)
    if args.command == "rebuild":
        print(json.dumps(rebuild_runtime(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "start":
        print(json.dumps(start_runtime(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "stop":
        print(json.dumps(stop_runtime(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(asdict(runtime_status()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
