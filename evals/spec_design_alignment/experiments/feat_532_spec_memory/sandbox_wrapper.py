"""Execute one evaluation role under a macOS filesystem confinement profile."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


GIT_METADATA_NAMES = {".git", ".evaluation-git"}
READABLE_ROOT_LABELS = ["role_runtime", "system_runtime", "workspace"]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _visible_files(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if name not in GIT_METADATA_NAMES and not (current_path / name).is_symlink()
        )
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root)
            if path.is_symlink() or any(
                part in GIT_METADATA_NAMES for part in relative.parts
            ):
                continue
            entries.append(
                {
                    "path": relative.as_posix(),
                    "sha256": _sha256_bytes(path.read_bytes()),
                }
            )
    return sorted(entries, key=lambda entry: entry["path"])


def _scheme_string(value: Path) -> str:
    return json.dumps(str(value.resolve(strict=False)))


def _sibling_denials(allowed_roots: list[Path], boundary: Path) -> list[Path]:
    allowed_roots = [path.resolve() for path in allowed_roots]
    boundary = boundary.resolve()
    if any(root != boundary and boundary not in root.parents for root in allowed_roots):
        raise ValueError("readable root is outside its confinement boundary")
    denied: list[Path] = []
    directories = {boundary}
    for root in allowed_roots:
        directories.update(
            parent for parent in root.parents if boundary in (parent, *parent.parents)
        )
    for directory in directories:
        if boundary != directory and boundary not in directory.parents:
            continue
        for entry in directory.iterdir():
            if not any(
                entry == root or entry in root.parents for root in allowed_roots
            ):
                denied.append(entry)
    return denied


def _sandbox_profile(
    *,
    workspace: Path,
    workspace_boundary: Path,
    artifacts: Path,
    runtime_root: Path,
    host_home: Path,
    network_process: Path,
    workspace_write: bool,
) -> str:
    confinement_boundary = Path(
        os.path.commonpath([workspace_boundary.resolve(), runtime_root.resolve()])
    )
    if confinement_boundary in {Path("/"), Path("/private"), Path("/Users")}:
        raise ValueError(
            f"role roots do not share a safe temporary boundary: {confinement_boundary}"
        )
    denied = [host_home.resolve(), artifacts.resolve()]
    denied.extend(_sibling_denials([workspace, runtime_root], confinement_boundary))
    unique = sorted({path.resolve(strict=False) for path in denied}, key=str)
    network_process = network_process.resolve()
    rules = [
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        f"(with-filter (process-path {_scheme_string(network_process)})",
        "  (allow network*))",
    ]
    for path in unique:
        matcher = "subpath" if path.is_dir() else "literal"
        rules.append(
            f"(deny file-read* file-write* ({matcher} {_scheme_string(path)}))"
        )
    if not workspace_write:
        rules.append(f"(deny file-write* (subpath {_scheme_string(workspace)}))")
    return "\n".join(rules) + "\n"


def _normalize_argument(
    value: str,
    *,
    workspace: Path,
    runtime_root: Path,
    artifacts: Path,
    host_home: Path,
) -> str:
    replacements = (
        (str(workspace), "$ROLE_WORKSPACE"),
        (str(runtime_root), "$ROLE_RUNTIME"),
        (str(artifacts), "$ARTIFACTS_ROOT"),
        (str(host_home), "$HOST_HOME"),
    )
    for source, label in replacements:
        value = value.replace(source, label)
    return value


def _command_execution_observed(stdout: str) -> bool:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "command_execution":
            return True
    return False


def execute_confined(
    *,
    manifest_id: str,
    command: list[str],
    workspace: Path,
    workspace_boundary: Path,
    artifacts: Path,
    runtime_root: Path,
    host_home: Path,
    environment: dict[str, str],
    envelope: str,
    actual_path: Path,
    workspace_write: bool,
) -> subprocess.CompletedProcess[str]:
    """Run a child process and independently persist its actual confinement facts."""
    workspace = workspace.resolve()
    workspace_boundary = workspace_boundary.resolve()
    artifacts = artifacts.resolve()
    runtime_root = runtime_root.resolve()
    host_home = host_home.resolve()
    canary = workspace_boundary / ".role-context-canary"
    if not canary.is_file():
        raise RuntimeError(f"role confinement canary is missing: {canary}")
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "tmp").mkdir(parents=True, exist_ok=True)
    profile = _sandbox_profile(
        workspace=workspace,
        workspace_boundary=workspace_boundary,
        artifacts=artifacts,
        runtime_root=runtime_root,
        host_home=host_home,
        network_process=Path(command[0]),
        workspace_write=workspace_write,
    )
    profile_sha256 = _sha256_bytes(profile.encode("utf-8"))
    confined_prefix = ["/usr/bin/sandbox-exec", "-p", profile]
    probe = subprocess.run(
        [*confined_prefix, "/bin/cat", str(canary)],
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        raise RuntimeError("role confinement canary was readable")
    network_probe = subprocess.run(
        [
            *confined_prefix,
            "/usr/bin/python3",
            "-c",
            'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0))',
        ],
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if network_probe.returncode == 0:
        raise RuntimeError("role tool network probe was permitted")
    initial_files = _visible_files(workspace)
    result = subprocess.run(
        [*confined_prefix, *command],
        cwd=workspace,
        input=envelope,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    actual: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_id": manifest_id,
        "formal_eligible": False,
        "cwd": "workspace",
        "resolved_argv": [
            _normalize_argument(
                value,
                workspace=workspace,
                runtime_root=runtime_root,
                artifacts=artifacts,
                host_home=host_home,
            )
            for value in command
        ],
        "environment_policy": {
            "keys": sorted(environment),
            "home": "role_runtime/home",
            "codex_home": "role_runtime/codex-home",
            "tmpdir": "role_runtime/tmp",
        },
        "readable_roots": READABLE_ROOT_LABELS,
        "initial_visible_files": initial_files,
        "final_visible_files": _visible_files(workspace),
        "input_envelope_sha256": _sha256_bytes(envelope.encode("utf-8")),
        "tools": {
            "shell": True,
            "workspace_write": workspace_write,
            "network": False,
            "command_execution_observed": _command_execution_observed(result.stdout),
        },
        "os_sandbox": {
            "mechanism": "macos_sandbox_exec_seatbelt",
            "profile_sha256": profile_sha256,
            "canary_read_blocked": True,
            "tool_network_blocked": True,
        },
        "exit_code": result.returncode,
    }
    actual_path.parent.mkdir(parents=True, exist_ok=True)
    actual_path.write_text(
        json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
