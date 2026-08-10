"""Execute one evaluation role under a macOS filesystem confinement profile."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


GIT_METADATA_NAMES = {".git", ".evaluation-git"}
READABLE_ROOT_LABELS = [
    "role_runtime_except_credentials",
    "system_runtime",
    "workspace",
]


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


def _path_filters(paths: list[Path]) -> str:
    return " ".join(f"(subpath {_scheme_string(path)})" for path in paths)


def _system_runtime_roots() -> list[Path]:
    roots = [
        Path("/System"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/Library/Apple"),
        Path("/Library/Developer/CommandLineTools"),
        Path("/opt/homebrew"),
        Path("/private/etc/hosts"),
        Path("/private/etc/resolv.conf"),
        Path("/private/etc/ssl"),
    ]
    return [path for path in roots if path.exists()]


def _codex_paths(command: list[str], environment: dict[str, str]) -> list[Path]:
    configured = shutil.which("codex", path=environment.get("PATH"))
    values = [Path(configured)] if configured else []
    if command and Path(command[0]).name == "codex":
        values.append(Path(command[0]))
    return sorted(
        {value.resolve(strict=False) for value in values} | set(values), key=str
    )


def _sandbox_profile(
    *,
    workspace: Path,
    workspace_boundary: Path,
    artifacts: Path,
    runtime_root: Path,
    host_home: Path,
    command: list[str],
    environment: dict[str, str],
    workspace_write: bool,
) -> str:
    confinement_boundary = Path(
        os.path.commonpath([workspace_boundary.resolve(), runtime_root.resolve()])
    )
    if confinement_boundary in {Path("/"), Path("/private"), Path("/Users")}:
        raise ValueError(
            f"role roots do not share a safe temporary boundary: {confinement_boundary}"
        )
    if workspace.resolve() == runtime_root.resolve():
        raise ValueError("workspace and role runtime must be distinct")
    auth = runtime_root / "codex-home/auth.json"
    codex_paths = _codex_paths(command, environment)
    primary_is_codex = bool(command and Path(command[0]).name == "codex")
    system_roots = _system_runtime_roots()
    readable = [workspace, runtime_root, *system_roots]
    rules = [
        "(version 1)",
        "(deny default)",
        '(import "system.sb")',
        "(allow process*)",
        "(allow signal (target children))",
        "(allow file-read-metadata file-test-existence)",
        "(allow user-preference-read)",
        f"(allow file-read* file-test-existence {_path_filters(readable)})",
        f"(allow file-map-executable {_path_filters(system_roots)})",
        f"(allow file-write* (subpath {_scheme_string(runtime_root)}))",
        '(allow file-read* file-write-data (literal "/dev/tty"))',
        '(allow mach-lookup (global-name "com.apple.SecurityServer") '
        '(global-name "com.apple.SystemConfiguration.configd"))',
        f"(deny file-read* file-write* (literal {_scheme_string(auth)}))",
    ]
    for path in codex_paths:
        rules.append(f"(deny process-exec (literal {_scheme_string(path)}))")
    if primary_is_codex:
        primary = Path(command[0]).resolve(strict=False)
        rules.extend(
            [
                f"(with-filter (process-path {_scheme_string(primary)})",
                "  (allow network*)",
                f"  (allow file-read* (literal {_scheme_string(auth)})))",
            ]
        )
        for path in codex_paths:
            rules.append(
                '(with-filter (process-path "/usr/bin/sandbox-exec") '
                f"(allow process-exec (literal {_scheme_string(path)})))"
            )
    if workspace_write:
        rules.append(f"(allow file-write* (subpath {_scheme_string(workspace)}))")
    return "\n".join(rules) + "\n"


def sandbox_profile_sha256(
    *,
    command: list[str],
    workspace: Path,
    workspace_boundary: Path,
    artifacts: Path,
    runtime_root: Path,
    host_home: Path,
    environment: dict[str, str],
    workspace_write: bool,
) -> str:
    """Return the identity of the exact role Seatbelt policy."""
    profile = _sandbox_profile(
        workspace=workspace.resolve(),
        workspace_boundary=workspace_boundary.resolve(),
        artifacts=artifacts.resolve(),
        runtime_root=runtime_root.resolve(),
        host_home=host_home.resolve(),
        command=command,
        environment=environment,
        workspace_write=workspace_write,
    )
    return _sha256_bytes(profile.encode("utf-8"))


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
        command=command,
        environment=environment,
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
    auth = runtime_root / "codex-home/auth.json"
    credential_probe = subprocess.run(
        [*confined_prefix, "/bin/cat", str(auth)],
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if credential_probe.returncode == 0:
        raise RuntimeError("role tool credential probe was readable")
    with tempfile.NamedTemporaryFile(
        prefix="feat-532-unrelated-read-", dir="/private/tmp", delete=False
    ) as handle:
        handle.write(b"unrelated role-context canary\n")
        unrelated = Path(handle.name)
    try:
        unrelated_probe = subprocess.run(
            [*confined_prefix, "/bin/cat", str(unrelated)],
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        unrelated.unlink(missing_ok=True)
    if unrelated_probe.returncode == 0:
        raise RuntimeError("unrelated host canary was readable")
    nested_codex_blocked = True
    nested_codex = shutil.which("codex", path=environment.get("PATH"))
    if nested_codex:
        nested_probe = subprocess.run(
            [
                *confined_prefix,
                "/bin/sh",
                "-c",
                '"$1" --version',
                "nested-codex-probe",
                nested_codex,
            ],
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        nested_codex_blocked = nested_probe.returncode != 0
        if not nested_codex_blocked:
            raise RuntimeError("nested Codex execution probe was permitted")
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
            "unrelated_read_blocked": True,
            "credential_read_blocked": True,
            "nested_codex_blocked": nested_codex_blocked,
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
